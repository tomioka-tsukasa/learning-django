"""
AlarmBox データ格納用 Django Models

使用方法:
1. このファイルの内容を適切なDjangoアプリの models.py に追加
2. python manage.py makemigrations
3. python manage.py migrate
"""

from django.db import models


class AlarmboxCreditCheck(models.Model):
    """
    AlarmBox 信用チェック結果

    AlarmBox APIから取得した信用チェックの基本情報を格納します。
    """

    class Result(models.TextChoices):
        """判定結果の選択肢"""
        OK = 'ok', '低リスク'
        HOLD = 'hold', '中リスク'
        NG = 'ng', '高リスク'

    # 主キー（UUIDv7）
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,  # Python 3.11未満の場合。3.11以上なら uuid.uuid7 または uuid7ライブラリ使用
        editable=False,
        verbose_name='ID',
    )

    # 外部キー
    client = models.ForeignKey(
        'Client',  # 既存のClientモデルを参照（アプリ名が異なる場合は 'app_name.Client' に変更）
        on_delete=models.PROTECT,
        related_name='alarmbox_credit_checks',
        verbose_name='クライアント',
    )

    # AlarmBox API から取得したデータ
    credit_check_id = models.IntegerField(
        verbose_name='AlarmBox信用チェックID',
        help_text='AlarmBox API側で発行されるID',
    )
    corporation_number = models.CharField(
        max_length=13,
        verbose_name='法人番号',
        help_text='13桁の法人番号',
    )
    company_name = models.CharField(
        max_length=255,
        verbose_name='企業名',
    )
    result = models.CharField(
        max_length=10,
        choices=Result.choices,
        null=True,
        blank=True,
        verbose_name='判定結果',
        help_text='ok=低リスク, hold=中リスク, ng=高リスク',
    )
    purchased_at = models.DateTimeField(
        verbose_name='購入日',
    )
    expired_at = models.DateTimeField(
        verbose_name='有効期限',
    )

    # PDF格納先（GCS）
    pdf_file_path = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name='PDFファイルパス',
        help_text='GCSのパス（例: gs://bucket/credit_checks/12345.pdf）',
    )

    # タイムスタンプ
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='作成日時',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新日時',
    )

    class Meta:
        db_table = 'hansha_alarmbox_credit_checks'
        verbose_name = 'AlarmBox信用チェック'
        verbose_name_plural = 'AlarmBox信用チェック'
        indexes = [
            models.Index(fields=['client'], name='idx_client_id'),
            models.Index(fields=['credit_check_id'], name='idx_credit_check_id'),
            models.Index(fields=['corporation_number'], name='idx_corporation_number'),
            models.Index(fields=['purchased_at'], name='idx_purchased_at'),
        ]

    def __str__(self):
        return f'{self.company_name} ({self.credit_check_id})'


class AlarmboxCreditCheckInfo(models.Model):
    """
    AlarmBox 信用チェック リスク情報

    企業に関するリスク情報の履歴を格納します。
    1つの信用チェックに対して複数のリスク情報が紐づきます。
    """

    # 外部キー
    alarmbox_credit_check = models.ForeignKey(
        AlarmboxCreditCheck,
        on_delete=models.CASCADE,
        related_name='infos',
        verbose_name='信用チェック',
    )

    # AlarmBox API から取得したデータ（infos.tags の展開）
    received_on = models.DateField(
        verbose_name='情報発生日',
    )
    tag = models.CharField(
        max_length=100,
        verbose_name='タグ名',
        help_text='例: 業績、登記変更、人事',
    )
    description = models.TextField(
        verbose_name='詳細説明',
    )
    source = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='情報ソース',
        help_text='例: 財務、登記情報、ニュース',
    )

    # タイムスタンプ
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='作成日時',
    )

    class Meta:
        db_table = 'hansha_alarmbox_credit_check_infos'
        verbose_name = 'AlarmBox信用チェック リスク情報'
        verbose_name_plural = 'AlarmBox信用チェック リスク情報'
        indexes = [
            models.Index(fields=['alarmbox_credit_check'], name='idx_info_credit_check_id'),
        ]

    def __str__(self):
        return f'{self.tag} ({self.received_on})'


# ============================================
# 使用例
# ============================================

"""
# データ保存の例

from myapp.models import AlarmboxCreditCheck, AlarmboxCreditCheckInfo

# APIレスポンスから保存
def save_credit_check(client_id, api_response, pdf_gcs_path=None):
    credit_check_data = api_response['credit_check']

    # メインテーブルに保存
    credit_check = AlarmboxCreditCheck.objects.create(
        client_id=client_id,
        credit_check_id=credit_check_data['credit_check_id'],
        corporation_number=credit_check_data['corporation_number'],
        company_name=credit_check_data['corporation_name'],
        result=credit_check_data.get('result'),
        purchased_at=credit_check_data['purchase_date'],
        expired_at=credit_check_data['expiration_date'],
        pdf_file_path=pdf_gcs_path,
    )

    # リスク情報を保存
    for info in credit_check_data.get('infos', []):
        for tag in info.get('tags', []):
            AlarmboxCreditCheckInfo.objects.create(
                alarmbox_credit_check=credit_check,
                received_on=info['received_date'],
                tag=tag['name'],
                description=tag['description'],
                source=tag.get('source'),
            )

    return credit_check


# データ取得の例

# 特定クライアントの信用チェック一覧
credit_checks = AlarmboxCreditCheck.objects.filter(
    client_id=100
).order_by('-purchased_at')

# 特定企業のリスク情報一覧
infos = AlarmboxCreditCheckInfo.objects.filter(
    alarmbox_credit_check__corporation_number='1234567890123'
).select_related('alarmbox_credit_check').order_by('-received_on')

# 「業績」に関するリスクがある企業一覧
credit_checks_with_performance_risk = AlarmboxCreditCheck.objects.filter(
    infos__tag='業績'
).distinct()
"""
