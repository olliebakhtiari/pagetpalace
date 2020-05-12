# Python standard.
import json

# Third-party.
import boto3


def get_config_dict_from_s3(s3_file_path):
    client = boto3.client('s3')
    result = client.get_object(Bucket='pagetpalace', Key=s3_file_path)
    json_string = result['Body'].read().decode()

    return json.loads(json_string)

