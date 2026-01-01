-- ============================================
-- AlarmBox データ格納テーブル作成SQL
-- ============================================

-- --------------------------------------------
-- 1. トークン管理テーブル: hansha_alarmbox_tokens
-- --------------------------------------------
-- AlarmBox API のアクセストークン・リフレッシュトークンを保存
-- 常に1レコードのみ存在（id=1 固定）

CREATE TABLE hansha_alarmbox_tokens (
    id INT PRIMARY KEY DEFAULT 1 COMMENT '主キー',
    access_token VARCHAR(512) NOT NULL COMMENT 'アクセストークン',
    refresh_token VARCHAR(512) NOT NULL COMMENT 'リフレッシュトークン',
    expired_at DATETIME DEFAULT NULL COMMENT 'access_tokenの有効期限',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',

    -- 1レコードのみ許可
    CONSTRAINT chk_single_row CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='AlarmBox API トークン管理';


-- --------------------------------------------
-- 2. メインテーブル: hansha_alarmbox_credit_checks
-- --------------------------------------------
-- AlarmBox APIから取得した信用チェックの基本情報を格納

CREATE TABLE hansha_alarmbox_credit_checks (
    id CHAR(32) PRIMARY KEY COMMENT '主キー（UUIDv7）',
    client_id INT NOT NULL COMMENT 'クライアントID',
    credit_check_id INT DEFAULT NULL COMMENT 'AlarmBox側 信用チェックID',
    corporation_number VARCHAR(13) NOT NULL COMMENT '法人番号（13桁）',
    company_name VARCHAR(255) DEFAULT NULL COMMENT '企業名',
    result VARCHAR(10) DEFAULT NULL COMMENT '判定結果（ok/hold/ng/null）',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'ステータス',
    purchased_at DATETIME DEFAULT NULL COMMENT '購入日',
    expired_at DATETIME DEFAULT NULL COMMENT '有効期限',
    pdf_file_path VARCHAR(500) DEFAULT NULL COMMENT 'PDFファイルのGCSパス',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',

    -- インデックス
    INDEX idx_client_id (client_id),
    INDEX idx_credit_check_id (credit_check_id),
    INDEX idx_corporation_number (corporation_number),
    INDEX idx_purchased_at (purchased_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='AlarmBox 信用チェック結果';


-- --------------------------------------------
-- 3. リスク情報テーブル: hansha_alarmbox_credit_check_infos
-- --------------------------------------------
-- 企業に関するリスク情報の履歴を格納

CREATE TABLE hansha_alarmbox_credit_check_infos (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主キー',
    alarmbox_credit_check_id CHAR(32) NOT NULL COMMENT '信用チェックID',
    received_on DATE NOT NULL COMMENT '情報発生日',
    tag VARCHAR(100) NOT NULL COMMENT 'タグ名',
    description TEXT NOT NULL COMMENT '詳細説明',
    source VARCHAR(100) DEFAULT NULL COMMENT '情報ソース',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',

    -- 外部キー制約
    CONSTRAINT fk_hansha_alarmbox_credit_check_infos_credit_check
        FOREIGN KEY (alarmbox_credit_check_id) REFERENCES hansha_alarmbox_credit_checks(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- インデックス
    INDEX idx_credit_check_id (alarmbox_credit_check_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='AlarmBox 信用チェック リスク情報';


-- ============================================
-- サンプルデータ投入（テスト用）
-- ============================================

-- メインテーブルにデータ投入
-- INSERT INTO alarmbox_credit_checks (
--     client_id,
--     credit_check_id,
--     corporation_number,
--     corporation_name,
--     result,
--     purchase_date,
--     expiration_date,
--     expired,
--     pdf_file_path
-- ) VALUES (
--     100,
--     12345,
--     '1234567890123',
--     '株式会社サンプル',
--     'hold',
--     '2025-12-18',
--     '2026-12-18',
--     FALSE,
--     'gs://bucket/credit_checks/12345.pdf'
-- );

-- リスク情報テーブルにデータ投入
-- INSERT INTO alarmbox_credit_check_infos (
--     alarmbox_credit_check_id,
--     received_date,
--     name,
--     description,
--     source
-- ) VALUES
--     (1, '2025-12-01', '業績', '売上低迷', '財務'),
--     (1, '2025-12-01', '人事', '大量退職', 'ニュース'),
--     (1, '2025-11-15', '登記変更', '本店移転', '登記情報');
