import base64
import logging
from datetime import datetime
from io import BytesIO

from core.models.riskeyes_v2.alarmbox import (
    HanshaAlarmboxCreditCheck,
    HanshaAlarmboxCreditCheckInfo,
)
from lib.alarmbox.client import AlarmboxClient
from lib.alarmbox.token_service import TokenService
from lib.alarmbox.types import CreditCheckResponse
from lib.gcs_client import GCSClient

logger = logging.getLogger(__name__)


class CreditCheckService:
    """
    信用チェック 購入〜保存サービス
    """

    GCS_FEATURE_NAME = "alarmbox"

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
        # 1. 有効なアクセストークンを取得
        access_token = TokenService.get_valid_access_token()
        client = AlarmboxClient(access_token)

        # 2. 信用チェックを購入
        logger.info(f"信用チェック購入開始: {corporation_number}")
        purchase_result = client.purchase_credit_check(
            corporation_number=corporation_number,
            deal=deal,
            purchase_reasons=purchase_reasons,
            purchase_reason_comment=purchase_reason_comment,
        )
        credit_check_id = purchase_result["credit_check"]["credit_check_id"]
        logger.info(f"信用チェック購入完了: credit_check_id={credit_check_id}")

        # 3. 信用チェック詳細取得
        logger.info(f"信用チェック詳細取得開始: credit_check_id={credit_check_id}")
        detail = client.get_credit_check(credit_check_id, with_pdf=True)
        logger.info("信用チェック詳細取得完了")

        # 4. PDFをGCSに保存
        pdf_file_path = None
        if detail.get("pdf_file_data"):
            pdf_file_path = cls._save_pdf_to_gcs(
                client_id=client_id,
                credit_check_id=credit_check_id,
                pdf_base64=detail["pdf_file_data"],
            )
            logger.info(f"PDF保存完了: {pdf_file_path}")

        # 5. DBに保存
        credit_check = cls._save_to_db(client_id, detail, pdf_file_path)
        logger.info(f"DB保存完了: id={credit_check.id}")

        return credit_check

    @classmethod
    def _save_to_db(
        cls, client_id: int, detail: CreditCheckResponse, pdf_file_path: str | None
    ) -> HanshaAlarmboxCreditCheck:
        # メインテーブルに保存（idはモデルのdefaultで自動生成）
        credit_check = HanshaAlarmboxCreditCheck.objects.create(
            client_id=client_id,
            credit_check_id=detail["credit_check_id"],
            corporation_number=detail["corporation_number"],
            company_name=detail["corporation_name"],
            result=detail.get("result"),
            purchased_at=datetime.strptime(detail["purchase_date"], "%Y-%m-%d"),
            expired_at=datetime.strptime(detail["expiration_date"], "%Y-%m-%d"),
            pdf_file_path=pdf_file_path,
        )

        # リスク情報テーブルに保存
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

        return credit_check

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
