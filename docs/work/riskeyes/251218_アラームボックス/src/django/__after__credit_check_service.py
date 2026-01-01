import base64
import logging
import traceback
from datetime import datetime
from io import BytesIO

from core.lib.lock import LockManager
from core.models.riskeyes_v2.alarmbox import (
    HanshaAlarmboxCreditCheck,
    HanshaAlarmboxCreditCheckInfo,
)
from lib.alarmbox.client import AlarmboxClient
from lib.alarmbox.exceptions import AlarmboxAPIError
from lib.alarmbox.token_service import TokenService
from lib.alarmbox.types import CreditCheckResponse
from lib.gcs_client import GCSClient

logger = logging.getLogger(__name__)


class CreditCheckService:
    """
    信用チェック 購入〜保存サービス
    """

    GCS_FEATURE_NAME = "alarmbox"
    LOCK_NAME = "alarmbox_credit_check"

    @classmethod
    def purchase_and_save(
        cls,
        client_id: int,
        corporation_number: str,
        deal: int | None = None,
        purchase_reasons: list[int] | None = None,
        purchase_reason_comment: str | None = None,
    ) -> HanshaAlarmboxCreditCheck:
        """
        信用チェックを購入し、結果をDBに保存する

        Args:
            client_id: RiskEyes のクライアントID
            corporation_number: 13桁の法人番号
            deal: 取引関係 (1=有, 2=無, 9=その他)
            purchase_reasons: 購入理由IDの配列
            purchase_reason_comment: 購入理由コメント

        Returns:
            保存した HanshaAlarmboxCreditCheck インスタンス
        """
        # ユーザー単位でロック（重複購入防止）
        lock_manager = LockManager(name=f"{cls.LOCK_NAME}_{client_id}", parallelism=1)

        with lock_manager.lock(timeout=60):
            # 1. 既存チェック（同じ法人番号で pending/success がある場合はエラー）
            existing = HanshaAlarmboxCreditCheck.objects.filter(
                client_id=client_id,
                corporation_number=corporation_number,
                status__in=[
                    HanshaAlarmboxCreditCheck.Status.PENDING,
                    HanshaAlarmboxCreditCheck.Status.SUCCESS,
                ],
            ).exists()

            if existing:
                raise AlarmboxAPIError("この法人番号は処理中または購入済みです")

            # 2. pending でレコード作成
            credit_check = HanshaAlarmboxCreditCheck.objects.create(
                client_id=client_id,
                corporation_number=corporation_number,
                status=HanshaAlarmboxCreditCheck.Status.PENDING,
            )

            # 3. 有効なアクセストークンを取得
            access_token = TokenService.get_valid_access_token()
            client = AlarmboxClient(access_token)

            # 4. 信用チェックを購入
            try:
                logger.info(f"信用チェック購入開始: {corporation_number}")
                purchase_result = client.purchase_credit_check(
                    corporation_number=corporation_number,
                    deal=deal,
                    purchase_reasons=purchase_reasons,
                    purchase_reason_comment=purchase_reason_comment,
                )
                credit_check_id = purchase_result["credit_check"]["credit_check_id"]
                logger.info(f"信用チェック購入完了: credit_check_id={credit_check_id}")
            except Exception:
                # 購入失敗 -> error（リトライ可能）
                credit_check.status = HanshaAlarmboxCreditCheck.Status.ERROR
                credit_check.save()
                logger.error(f"信用チェック購入失敗: {traceback.format_exc()}")
                raise

            # ---- ここから先は購入成功後なので、絶対に例外を投げない ----

            # 5. 信用チェック詳細取得（失敗しても続行）
            detail = None
            try:
                logger.info(
                    f"信用チェック詳細取得開始: credit_check_id={credit_check_id}"
                )
                detail = client.get_credit_check(credit_check_id, with_pdf=True)
                logger.info("信用チェック詳細取得完了")
            except Exception:
                logger.error(
                    f"信用チェック詳細取得失敗: credit_check_id={credit_check_id}\n{traceback.format_exc()}"
                )

            # 6. PDFをGCSに保存（失敗しても続行）
            pdf_file_path = None
            if detail and detail.get("pdf_file_data"):
                try:
                    pdf_file_path = cls._save_pdf_to_gcs(
                        client_id=client_id,
                        credit_check_id=credit_check_id,
                        pdf_base64=detail["pdf_file_data"],
                    )
                    logger.info(f"PDF保存完了: {pdf_file_path}")
                except Exception:
                    logger.error(
                        f"PDF保存失敗: credit_check_id={credit_check_id}\n{traceback.format_exc()}"
                    )

            # 7. レコード更新（取得できた情報だけで success）
            credit_check.credit_check_id = credit_check_id
            credit_check.status = HanshaAlarmboxCreditCheck.Status.SUCCESS
            credit_check.pdf_file_path = pdf_file_path

            if detail:
                cls._update_credit_check(credit_check, detail)

            # 8. リスク情報テーブルに保存
            if detail:
                cls._save_infos(credit_check, detail)

            logger.info(f"DB保存完了: id={credit_check.id}")

            return credit_check

    @classmethod
    def _update_credit_check(
        cls, credit_check: HanshaAlarmboxCreditCheck, detail: CreditCheckResponse
    ) -> None:
        """詳細情報でレコードを更新"""
        credit_check.company_name = detail.get("corporation_name")
        credit_check.result = detail.get("result")

        if detail.get("purchase_date"):
            credit_check.purchased_at = datetime.strptime(
                detail["purchase_date"], "%Y-%m-%d"
            )
        if detail.get("expiration_date"):
            credit_check.expired_at = datetime.strptime(
                detail["expiration_date"], "%Y-%m-%d"
            )

        credit_check.save()

    @classmethod
    def _save_infos(
        cls, credit_check: HanshaAlarmboxCreditCheck, detail: CreditCheckResponse
    ) -> None:
        """リスク情報テーブルに保存"""
        infos_to_create = []
        for info in detail.get("infos", []):
            received_date = datetime.strptime(info["received_date"], "%Y-%m-%d").date()
            for tag in info.get("tags", []):
                infos_to_create.append(
                    HanshaAlarmboxCreditCheckInfo(
                        alarmbox_credit_check=credit_check,
                        received_on=received_date,
                        tag=tag["name"],
                        description=tag["description"],
                        source=tag.get("source"),
                    )
                )

        if infos_to_create:
            HanshaAlarmboxCreditCheckInfo.objects.bulk_create(infos_to_create)

    @classmethod
    def _save_pdf_to_gcs(
        cls,
        client_id: int,
        credit_check_id: int,
        pdf_base64: str,
    ) -> str:
        """
        Base64エンコードされたPDFをGCSに保存

        Returns:
            GCSのファイルパス
        """
        # Base64デコード
        pdf_bytes = base64.b64decode(pdf_base64)
        pdf_file = BytesIO(pdf_bytes)

        # GCSにアップロード
        gcs_client = GCSClient()
        file_path = gcs_client.upload_file(
            source_file=pdf_file,
            client_id=client_id,
            feature_name=cls.GCS_FEATURE_NAME,
            filename=f"credit_check_{credit_check_id}.pdf",
        )

        return file_path
