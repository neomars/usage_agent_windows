# setup_database.py
import getpass
import configparser
import sys
import os
import messages # Import the new messages module

try:
    import mariadb
except ImportError:
    print(messages.SETUP_ERROR_MARIADB_MODULE_IMPORT)
    sys.exit(1)

try:
    from sql_ddl import ALL_TABLES_DDL
except ImportError:
    print(messages.SETUP_ERROR_SQLDDL_IMPORT)
    sys.exit(1)

def setup_database():
    print(messages.SETUP_HEADER)
    print(messages.SETUP_INTRO_MAIN)
    print(messages.SETUP_INTRO_ASSUMPTION_HEADER)
    print(messages.SETUP_INTRO_ASSUMPTION_DETAIL)
    print(messages.SETUP_PRE_REQUISITE_DB_RUNNING)

    app_db_host = input(f"Enter MariaDB host for the application database [{messages.SETUP_PROMPT_DB_HOST_DEFAULT}]: ").strip()
    if not app_db_host:
        app_db_host = messages.SETUP_PROMPT_DB_HOST_DEFAULT

    app_db_name = input(f"Enter the name of the existing application database [{messages.SETUP_PROMPT_DB_NAME_DEFAULT}]: ").strip()
    if not app_db_name:
        app_db_name = messages.SETUP_PROMPT_DB_NAME_DEFAULT

    app_db_user = input(f"Enter the existing application username for database '{app_db_name}' [{messages.SETUP_PROMPT_DB_USER_DEFAULT}]: ").strip()
    if not app_db_user:
        app_db_user = messages.SETUP_PROMPT_DB_USER_DEFAULT

    while True:
        app_db_pass = getpass.getpass(f"Enter password for application user '{app_db_user}': ")
        if not app_db_pass:
            print(messages.SETUP_ERROR_PASSWORD_EMPTY)
            continue
        app_db_pass_confirm = getpass.getpass(f"Confirm password for '{app_db_user}': ")
        if app_db_pass == app_db_pass_confirm:
            break
        else:
            print(messages.SETUP_ERROR_PASSWORD_MISMATCH)

    print(messages.SETUP_SUMMARY_HEADER)
    print(messages.SETUP_SUMMARY_DB_HOST.format(app_db_host))
    print(messages.SETUP_SUMMARY_DB_NAME.format(app_db_name))
    print(messages.SETUP_SUMMARY_DB_USER.format(app_db_user))
    print(messages.SETUP_SUMMARY_DB_PASSWORD_SET)
    print(messages.SETUP_SUMMARY_REVIEW_PROMPT_1)
    print(messages.SETUP_SUMMARY_REVIEW_PROMPT_2)

    if input("\nProceed with these actions? (yes/no): ").strip().lower() != 'yes':
        print(messages.SETUP_ABORTED_BY_USER)
        sys.exit(0)

    # 1. Connect as App User and Create Tables
    app_conn = None
    app_cursor = None
    print(messages.SETUP_STEP1_HEADER.format(app_db_name, app_db_host, app_db_user))
    try:
        app_conn = mariadb.connect(
            host=app_db_host,
            user=app_db_user,
            password=app_db_pass,
            database=app_db_name
        )
        print(messages.SETUP_STEP1_CONNECT_SUCCESS.format(app_db_name))
        app_cursor = app_conn.cursor()

        print(messages.SETUP_STEP1_CREATING_TABLES)
        for ddl_statement in ALL_TABLES_DDL:
            app_cursor.execute(ddl_statement)
        app_conn.commit()
        print(messages.SETUP_STEP1_TABLES_SUCCESS.format(app_db_name))

    except mariadb.Error as e:
        if app_conn:
            try:
                app_conn.rollback()
                print(messages.SETUP_STEP1_ERROR_ROLLBACK)
            except mariadb.Error as rb_err:
                print(messages.SETUP_STEP1_ERROR_ROLLBACK_FAILED.format(rb_err))

        print(messages.SETUP_STEP1_ERROR_TABLE_CREATION.format(e)) # Original MariaDB error
        print(messages.SETUP_GUIDANCE_HEADER)
        print(messages.SETUP_GUIDANCE_DB_RUNNING.format(app_db_host))
        print(messages.SETUP_GUIDANCE_DB_EXISTS.format(app_db_name))
        print(messages.SETUP_GUIDANCE_USER_EXISTS_PASSWORD.format(app_db_user))
        print(messages.SETUP_GUIDANCE_USER_PERMISSIONS.format(app_db_user, app_db_name))
        sys.exit(1)
    except Exception as e:
        if app_conn:
            try:
                app_conn.rollback()
            except mariadb.Error as rb_err:
                print(messages.SETUP_STEP1_ERROR_ROLLBACK_FAILED.format(rb_err))
        print(messages.SETUP_STEP1_ERROR_TABLE_CREATION_UNEXPECTED.format(e))
        sys.exit(1)
    finally:
        if app_cursor: app_cursor.close()
        if app_conn: app_conn.close()

    # 2. Create db_config.ini
    print(messages.SETUP_STEP2_HEADER)
    config = configparser.ConfigParser()
    config['database'] = {
        'host': app_db_host,
        'name': app_db_name,
        'user': app_db_user,
        'password': app_db_pass
    }

    try:
        with open('db_config.ini', 'w') as configfile:
            config.write(configfile)
        print(messages.SETUP_STEP2_DBCONFIG_CREATED)
        print(messages.SETUP_STEP2_DBCONFIG_REMINDER_SECURE)
        print(messages.SETUP_STEP2_DBCONFIG_REMINDER_GITIGNORE)
    except IOError as e:
        print(messages.SETUP_STEP2_ERROR_DBCONFIG_WRITE.format(e))
        sys.exit(1)

    print(messages.SETUP_FINAL_SUCCESS_HEADER)
    print(messages.SETUP_FINAL_SUCCESS_DETAIL.format(app_db_name))
    print(messages.SETUP_FINAL_SUCCESS_NEXT_STEP.format(app_db_name, app_db_host, app_db_user))

if __name__ == "__main__":
    setup_database()
