import requests
import xml.etree.ElementTree as ET
import boto3
import smtplib
from email.mime.text import MIMEText
import sqlite3
import json

def get_latest_version(group_id, artifact_id):
    """Fetches the latest version of a Maven artifact from Maven Central."""
    metadata_url = f"https://repo1.maven.org/maven2/{group_id.replace('.', '/')}/{artifact_id}/maven-metadata.xml"
    try:
        response = requests.get(metadata_url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        latest_version = root.find(".//latest").text
        return latest_version
    except requests.exceptions.RequestException as e:
        print(f"Error fetching metadata: {e}")
        return None
    except (AttributeError, ET.ParseError) as e:
        print(f"Error parsing metadata: {e}")
        return None

def get_current_version_from_db(group_id, artifact_id, db_path="artifact_versions.db"):
    """Retrieves the current version from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table if it doesn't exist.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS versions (
                group_id TEXT,
                artifact_id TEXT,
                version TEXT,
                PRIMARY KEY (group_id, artifact_id)
            )
        """)

        cursor.execute("SELECT version FROM versions WHERE group_id = ? AND artifact_id = ?", (group_id, artifact_id))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_current_version_in_db(group_id, artifact_id, version, db_path="artifact_versions.db"):
    """Updates the current version in the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS versions (
                group_id TEXT,
                artifact_id TEXT,
                version TEXT,
                PRIMARY KEY (group_id, artifact_id)
            )
        """)
        cursor.execute("REPLACE INTO versions (group_id, artifact_id, version) VALUES (?, ?, ?)", (group_id, artifact_id, version))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

def check_for_new_version(group_id, artifact_id):
    """Checks if a new version is available."""
    current_version = get_current_version_from_db(group_id, artifact_id)
    latest_version = get_latest_version(group_id, artifact_id)

    if latest_version and current_version and latest_version != current_version:
        return latest_version
    elif latest_version and current_version is None:
        return latest_version
    return None

def send_email(sender_email, receiver_email, subject, body):
    """Sends an email notification using AWS SES."""
    client = boto3.client('ses')  # No need to provide credentials explicitly when using an IAM role

    try:
        response = client.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': [receiver_email]
            },
            Message={
                'Subject': {
                    'Data': subject
                },
                'Body': {
                    'Text': {
                        'Data': body
                    }
                }
            }
        )
        print("Email notification sent successfully. Message ID:", response['MessageId'])
    except Exception as e:
        print(f"Error sending email: {e}")

def load_artifacts_from_json(filepath="artifacts.json"):
    """Loads artifact definitions from a JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {filepath} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {filepath}.")
        return []

def print_current_versions(db_path="artifact_versions.db"):
    """Prints all current versions from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT group_id, artifact_id, version FROM versions")
        rows = cursor.fetchall()
        if rows:
            print("Current Artifact Versions:")
            for row in rows:
                print(f"- {row[0]}:{row[1]} - {row[2]}")
        else:
            print("No artifact versions found in the database.")
        print("")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

def main():

    print_current_versions()

    artifacts = load_artifacts_from_json()
    email_settings = load_email_settings()

    if not email_settings:
        print("Error: Email settings not found. Exiting.")
        return

    print("New Versions:")

    for artifact in artifacts:
        group_id = artifact.get("group_id")
        artifact_id = artifact.get("artifact_id")

        if not group_id or not artifact_id:
            print("Warning: Missing group_id or artifact_id in JSON.")
            continue

        new_version = check_for_new_version(group_id, artifact_id)
        #print("Current version of " + group_id + "." + artifact_id + " is " + new_version)

        if new_version:
            print(f"- New version available for {group_id}:{artifact_id}: {new_version}")
            update_current_version_in_db(group_id, artifact_id, new_version)

            sender_email = "your_email@gmail.com"
            sender_password = "your_password"
            receiver_email = "recipient_email@example.com"

            subject = f"New Maven Artifact Version: {group_id}:{artifact_id}"
            body = f"A new version ({new_version}) of {group_id}:{artifact_id} is available.\nPrevious version: {get_current_version_from_db(group_id, artifact_id)}"

            #send_email(sender_email, receiver_email, subject, body)

            print(subject)
            print(body)


        else:
            print(f"- No new version available for {group_id}:{artifact_id}.")
            if get_current_version_from_db(group_id, artifact_id) is None:
                first_version = get_latest_version(group_id, artifact_id)
                update_current_version_in_db(group_id, artifact_id, first_version)
                print(f"- First version added to database for {group_id}:{artifact_id}: {first_version}")

if __name__ == "__main__":
    main()