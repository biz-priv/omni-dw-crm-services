import os
import json
import logging
import requests
import psycopg2
import pytz
import boto3
from decimal import Decimal
from datetime import datetime,timezone
import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

from src.common import modify_date
from src.common import update_date
from src.common import execute_db_query
from src.common import get_timestamp
from src.common import set_timestamp
from src.common import s3GetObject
from src.common import s3UploadObject

headers = {'content-type': 'application/json'}
tz = pytz.timezone('US/Central')
fmt = '%Y-%m-%d %H:%M:%S'

def handler(event, context):
    logger.info("Event: {}".format(json.dumps(event)))
    try:
        url = os.environ['salessummary_table_url']
        timestamp_param_name = os.environ['timestamp_parameter']
        bucket = os.environ['s3_bucket']
        key = os.environ['s3_key']
    except Exception as e:
        logging.exception("EnvironmentVariableError: {}".format(e))
        raise EnvironmentVariableError(json.dumps({"httpStatus": 400, "message": "Environment variable not set."}))

    if "start_from" in event:
        start_record = event["start_from"]
        s3_data = s3GetObject(bucket,key)
        records = eval(s3_data)
    else:
        start_record = 0
        records = initial_execution(timestamp_param_name,bucket,key)
    
    stop_record = (start_record + 100) if (start_record + 100) < len(records) else len(records)

    logger.info("Executing from array index {} to {}".format(start_record, stop_record))
    count = 0
    for record in records[start_record:stop_record]:

        count=count+1
        if count % 100 == 0:
            logger.info("Working on processing element number: {}".format(records.index(record)))
        data = json.dumps(convert_records(record))
        try:
            r = requests.post(url, headers=headers,data=data)
        except Exception as e:
            logging.exception("ApiPostError: {}".format(e))
            set_timestamp(timestamp_param_name, datetime.now(tz).strftime(fmt))
            raise ApiPostError(json.dumps({"httpStatus": 400, "message": "Api post error."}))
    
    logger.info("Execution complete!")
    event["start_from"] = stop_record
    if(stop_record != len(records)):
        logger.info("In progress")
        event["status"] = "InProgress"
    else:
        logger.info("completed!")
        event["status"] = "Completed"
        set_timestamp(timestamp_param_name, datetime.now(tz).strftime(fmt))
    return event

def initial_execution(param_name,bucket,key):

    time = get_timestamp(param_name)
    query = 'SELECT "bill to customer", "bill to number", "cntrolling customer", "cntrolling customer number", load_create_date, load_update_date, "month", "owner", "profit", "sales rep", "source system", "total charge", "total cost", "year", id FROM datamart.sales_summary WHERE (load_create_date >= \''+time+'\' OR load_update_date >= \''+time+'\')'
    queryData = execute_db_query(query)
    s3Data = s3UploadObject(queryData,'/tmp/sales_summary.txt',bucket,key)
    return execute_db_query(query)

def convert_records(data):
    try:
        record = {}
        record["bill to customer"] = data[0]
        record["bill to number"] = data[1]
        record["controlling customer"] = data[2]
        record["controlling customer number"] = data[3]
        record["global_name_match"] = str(data[10])+"-"+str(data[1])
        record["load_create_date"] = update_date(data[4]) 
        record["load_update_date"] = update_date(data[5]) 
        record["month"] = data[6]
        record["profit"] = float(data[8])
        record["sales rep"] = data[9]
        record["source_system"] = data[10]
        record["total charge"] = float(data[11])
        record["total cost"] = float(data[12])
        record["year"] = data[13]
        record["owner"] = ""
        record["unique_id"] = data[14]
        return record
    except Exception as e:
        logging.exception("RecordConversionError: {}".format(e))
        raise RecordConversionError(json.dumps({"httpStatus": 400, "message": "Record conversion error."}))
    
class EnvironmentVariableError(Exception): pass
class GetS3ObjectError(Exception): pass
class UpdateFileError(Exception): pass
class InitializationError(Exception): pass
class UpdateFileError(Exception): pass
class GetParameterError(Exception): pass
class RecordConversionError(Exception): pass
class ApiPostError(Exception): pass