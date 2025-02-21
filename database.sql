-- Krijo databazën
CREATE DATABASE IF NOT EXISTS fake_news_detection;

-- Përdor databazën
USE fake_news_detection;

-- Krijo tabelën users
CREATE TABLE IF NOT EXISTS users (
    id INT(11) AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    otp VARCHAR(6) DEFAULT NULL,
    otp_created_at DATETIME DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_admin TINYINT(1) DEFAULT 0
);

-- Shto një përdorues admin
INSERT INTO users (username, email, password, otp, otp_created_at, is_admin)
VALUES 
('admin', 'admin@example.com', 'admin_password', NULL, NULL, 1);
