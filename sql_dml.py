# sql_dml.py

# DML (Data Manipulation Language) SQL query strings.
# Using %s placeholders for MariaDB/MySQL connector.

# --- Queries for /log_activity endpoint ---
SELECT_COMPUTER_BY_NETBIOS = "SELECT id FROM computers WHERE netbios_name = %s"
UPDATE_COMPUTER_LAST_SEEN_IP = "UPDATE computers SET ip_address = %s, last_seen = NOW() WHERE id = %s"
INSERT_NEW_COMPUTER = "INSERT INTO computers (netbios_name, ip_address, last_seen) VALUES (%s, %s, NOW())"
INSERT_ACTIVITY_LOG = """
    INSERT INTO activity_logs
    (computer_id, timestamp, free_disk_space_gb, cpu_usage_percent, gpu_usage_percent, active_window_title)
    VALUES (%s, %s, %s, %s, %s, %s)
"""

# --- Queries for Group Management API (/api/groups/*) ---
INSERT_NEW_GROUP = "INSERT INTO computer_groups (name, description) VALUES (%s, %s)"
SELECT_ALL_GROUPS = "SELECT id, name, description FROM computer_groups ORDER BY name"
# SELECT_GROUP_BY_ID = "SELECT id, name, description FROM computer_groups WHERE id = %s" # Potentially useful
SELECT_GROUP_BY_NAME = "SELECT id FROM computer_groups WHERE name = %s" # Used in assign_group

# --- Queries for Assigning Computer to Group (/api/computers/.../assign_group) ---
# SELECT_COMPUTER_BY_NETBIOS is already defined above.
# SELECT_GROUP_BY_NAME is already defined above.
UPDATE_COMPUTER_GROUP_ID = "UPDATE computers SET group_id = %s WHERE id = %s"

# --- Queries for Dashboard (/ or /dashboard) ---
SELECT_COMPUTERS_FOR_DASHBOARD = """
    SELECT c.id, c.netbios_name, c.ip_address, c.last_seen, IFNULL(g.name, 'N/A') as group_name, g.id as group_id
    FROM computers c
    LEFT JOIN computer_groups g ON c.group_id = g.id
    ORDER BY c.last_seen DESC, c.netbios_name
"""
# Added c.id and g.id to the dashboard query for potential future use (e.g., linking to detail pages)


# --- Queries for Alerts (Conceptual - for future implementation) ---
# These are examples and may need adjustment or different approaches.

# Example: Get latest activity log for each computer to check recent stats
# This is complex and often better handled by application logic after fetching recent logs.
# SELECT_LATEST_ACTIVITY_FOR_COMPUTER = """
#    SELECT * FROM activity_logs al
#    WHERE al.computer_id = %s
#    ORDER BY al.timestamp DESC
#    LIMIT 1
# """

# Example: Computers with CPU usage above a threshold in their latest report
# This would typically involve a more complex query or application-side filtering.
# SELECT_COMPUTERS_WITH_RECENT_HIGH_CPU = """
#    SELECT c.netbios_name, c.ip_address, al.cpu_usage_percent, al.timestamp
#    FROM computers c
#    JOIN activity_logs al ON c.id = al.computer_id
#    WHERE al.id = (SELECT MAX(sub_al.id) FROM activity_logs sub_al WHERE sub_al.computer_id = c.id)
#    AND al.cpu_usage_percent > %s
# """

# Example: Computers that haven't reported in a while (e.g., last_seen older than X minutes/hours)
# SELECT_OFFLINE_COMPUTERS = "SELECT netbios_name, ip_address, last_seen FROM computers WHERE last_seen < (NOW() - INTERVAL %s MINUTE)"
# The %s here would be the number of minutes. The interval syntax might vary slightly by DB.

# Note: The dashboard alert section will likely involve more specific queries
# or processing of data fetched by more general queries.
# For now, these are just conceptual placeholders.
