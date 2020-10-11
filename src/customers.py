import os
import json
import logging
import requests
import psycopg2
import boto3
import pytz
from decimal import Decimal
from datetime import datetime
from datetime import timezone

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
        url = os.environ['customer_table_url']
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
            set_timestamp(timestamp_param_name, datetime.now(tz).strftime(fmt)) #changed the timestamp
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
    query = 'SELECT name, account_mgr, addr1, addr2, ap_email, bill_to_nbr, billto_only, city, controlling_nbr, controlling_only, country, cust_contact, email, load_create_date, load_update_date, nbr, owner, sales_rep, source_system, state, station, zip FROM public.customers WHERE (billto_only = \'Y\' OR controlling_only = \'Y\') AND (load_create_date >= \''+time+'\' OR load_update_date >= \''+time+'\')'
    queryData = execute_db_query(query)
    s3Data = s3UploadObject(queryData,'/tmp/customers.txt',bucket,key)
    return execute_db_query(query)

def convert_records(data):
    try:
        record = {}
        record["Name"] = data[0]
        record["account_mgr"] = data[1]
        record["Address_1"] = data[2]
        record["Address_2"] = data[3]
        record["ap_email"] = data[4]
        record["bill_to_nbr"] = data[5]
        record["billto_only"] = data[6]
        record["city"] = data[7]
        record["controlling_nbr"] = data[8]
        record["controlling_only"] = data[9]
        record["country"] = data[10]
        record["cust_contact"] = data[11]
        record["email"] = data[12]
        record["global_name_match"] = str(data[18])+"-"+str(data[15])
        record["load_create_date"] = update_date(data[13])
        record["load_update_date"] = update_date(data[14]) 
        record["nbr"] = data[15]
        record["owner"] = ""
        record["sales_rep"] = data[17]
        record["source_system"] = data[18]
        record["state"] = data[19]
        record["station"] = data[20]
        record["zip"] = data[21]
        return record
    except Exception as e:
        logging.exception("RecordConversionError: {}".format(e))
        raise RecordConversionError(json.dumps({"httpStatus": 400, "message": "Record conversion error."}))

class EnvironmentVariableError(Exception): pass
class GetS3ObjectError(Exception): pass
class InitializationError(Exception): pass
class UpdateFileError(Exception): pass
class GetParameterError(Exception): pass
class RecordConversionError(Exception): pass
class ApiPostError(Exception): pass
class UpdateFileError(Exception): pass
