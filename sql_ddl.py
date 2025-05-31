# sql_ddl.py

# SQL statements for creating tables if they don't exist.
# Using InnoDB engine for transaction support and foreign keys.

CREATE_COMPUTER_GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS computer_groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    INDEX idx_group_name (name)
) ENGINE=InnoDB;
"""

CREATE_COMPUTERS_TABLE = """
CREATE TABLE IF NOT EXISTS computers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    netbios_name VARCHAR(255) UNIQUE NOT NULL,
    ip_address VARCHAR(45),
    last_seen DATETIME,
    group_id INT,
    INDEX idx_computer_netbios_name (netbios_name),
    INDEX idx_computer_last_seen (last_seen),
    INDEX idx_computer_group_id (group_id), /* Added index for FK */
    FOREIGN KEY (group_id) REFERENCES computer_groups(id) ON DELETE SET NULL
) ENGINE=InnoDB;
"""

CREATE_ACTIVITY_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    computer_id INT NOT NULL,
    timestamp DATETIME NOT NULL,
    free_disk_space_gb FLOAT,
    cpu_usage_percent FLOAT,
    gpu_usage_percent FLOAT,
    active_window_title VARCHAR(512),
    INDEX idx_activity_computer_id_timestamp (computer_id, timestamp), /* Composite index */
    INDEX idx_activity_timestamp (timestamp), /* Separate index on timestamp can also be useful */
    FOREIGN KEY (computer_id) REFERENCES computers(id) ON DELETE CASCADE
) ENGINE=InnoDB;
"""

# A list to easily access all DDL statements in order of creation
ALL_TABLES_DDL = [
    CREATE_COMPUTER_GROUPS_TABLE,
    CREATE_COMPUTERS_TABLE,
    CREATE_ACTIVITY_LOGS_TABLE
]
