import os
import json
import boto3
import logging
import psycopg2
from datetime import datetime,timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def modify_date(x):
    try:
        if x == None:
            return 'null'
        else:
            return x.isoformat()
    except Exception as e:
        logging.exception("DateConversionError: {}".format(e))

def update_date(load_date):
    try:
        if load_date == None:
            return '9999-12-31 00:00:00'
        else:
            return load_date.strftime("%m/%d/%Y, %H:%M:%S")
    except Exception as e:
        logging.exception("UpdateDateError: {}".format(e))

def get_timestamp(param_name):
    try:
        client = boto3.client('ssm')
    except Exception as e:
        logging.exception("SsmInitializationError: {}".format(e))
        raise InitializationError(json.dumps({"httpStatus": 400, "message": "ssm initialization error."}))

    try:
        response = client.get_parameter(
            Name=param_name
        )
        return response["Parameter"]["Value"]
    except Exception as e:
        logging.exception("SsmGetParameterError: {}".format(e))
        raise GetParameterError(json.dumps({"httpStatus": 400, "message": "ssm get parameter error."}))

def set_timestamp(param_name, param_value):
    try:
        client = boto3.client('ssm')
    except Exception as e:
        logging.exception("SsmInitializationError: {}".format(e))
        raise InitializationError(json.dumps({"httpStatus": 400, "message": "ssm initialization error."}))

    try:
        client.put_parameter(
            Name=param_name,
            Value=param_value,
            Type='String',
            Overwrite=True
        )
    except Exception as e:
        logging.exception("SsmSetParameterError: {}".format(e))
        raise SetParameterError(json.dumps({"httpStatus": 400, "message": "ssm set parameter error."}))

def execute_db_query(query):
    try:
        con=psycopg2.connect(dbname = os.environ['db_name'], host=os.environ['db_host'],
                            port= os.environ['db_port'], user = os.environ['db_username'], password = os.environ['db_password'])
        con.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        cur.execute(query)
        con.commit()
        results = cur.fetchall()
        cur.close()
        con.close()
        return results
    except Exception as e:
        logging.exception("DatabaseError: {}".format(e))
        raise DatabaseError(json.dumps({"httpStatus": 400, "message": "Database error."}))

def s3GetObject(bucket,key):
    try:
        s3 = boto3.resource('s3')
    except Exception as e:
        logging.exception("S3InitializationError: {}".format(e))
        raise InitializationError(json.dumps({"httpStatus": 400, "message": "s3 initialization error."}))

    try:
        data = s3.Object(bucket, key).get()['Body'].read()
        return data

    except Exception as e:
        logging.exception("GetS3ObjectError: {}".format(e))
        raise GetS3ObjectError(json.dumps({"httpStatus": 400, "message": "S3 Get object error."}))

def s3UploadObject(queryData,filename,bucket,key):
    try:
        s3 = boto3.resource('s3')
    except Exception as e:
        logging.exception("S3InitializationError: {}".format(e))
        raise InitializationError(json.dumps({"httpStatus": 400, "message": "s3 initialization error."}))
        
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(str(queryData))
        s3.meta.client.upload_file(filename, bucket, key)
    except Exception as e:
        logging.exception("UpdateFileError: {}".format(e))
        raise UpdateFileError(json.dumps({"httpStatus": 400, "message": "Update file error."}))

class InitializationError(Exception): pass
class GetParameterError(Exception): pass
class SetParameterError(Exception): pass
class DatabaseError(Exception): pass
class GetS3ObjectError(Exception): pass
class UpdateFileError(Exception): pass
