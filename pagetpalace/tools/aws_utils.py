# Python standard.
import json

# Third-party.
import boto3


def get_config_dict_from_s3(s3_file_path: str):
    session = boto3.Session(profile_name='pagetpalace')
    client = session.client(service_name='s3')
    result = client.get_object(Bucket='account-configs', Key=s3_file_path)
    json_string = result['Body'].read().decode()

    return json.loads(json_string)

