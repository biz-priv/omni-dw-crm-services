import os
import json
import logging
import requests
import pytz
import boto3
import datetime
from decimal import Decimal
from datetime import datetime as dt
from datetime import timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

from src.common import modify_date
from src.common import execute_db_query
from src.common import get_timestamp
from src.common import set_timestamp
from src.common import s3GetObject
from src.common import s3UploadObject

headers = {'content-type': 'application/json'}
tz = pytz.timezone('US/Central')
fmt = '%Y-%m-%d %H:%M:%S'

sns = boto3.client('sns')

def handler(event, context):
    try:
        url = os.environ['globalcustomer_table_url']
        sns_topic_arn = "arn:aws:sns:us-east-1:332281781429:dynamics_crm_failures_global_customers"
        timestamp_param_name = os.environ['timestamp_parameter']
        bucket = os.environ['s3_bucket']
        key = os.environ['s3_key']
    except Exception as e:
        logging.exception("EnvironmentVariableError: {}".format(e))
        raise EnvironmentVariableError(json.dumps({"httpStatus": 400, "message": "Environment variable not set."}))

    if "start_from" in event:
        start_record = event["start_from"]
        logger.info("start record is :{}".format(start_record))
        s3_data = s3GetObject(bucket,key)
        records = eval(s3_data)
    else:
        start_record = 0
        records = initial_execution(timestamp_param_name,bucket,key)

    
    stop_record = (start_record + 100) if (start_record + 100) < len(records) else len(records)
    logger.info("stop record is :{}".format(stop_record))
    logger.info("Executing from array index {} to {}".format(start_record, stop_record))
    count = 0
    
    for record in records[start_record:stop_record]:
        
        count=count+1
        if count % 100 == 0:
            logger.info("Working on processing element number: {}".format(records.index(record)))
        data = json.dumps(convert_records(record))
        try:
            r = requests.post(url, headers=headers,data=data)
            
            if r.status_code != 200:
               results_failure = logger.info("record not inserted : {}".format(record[9]))
               sub = "Record was not inserted into Dynamics365 CRM"
               msg = "Record Information: "+data
               sns_notify(sub, msg, sns_topic_arn)
        except Exception as e:
            logging.exception("ApiPostError: {}".format(e))
            set_timestamp(timestamp_param_name, dt.now(tz).strftime(fmt)) #changed the timestamp
            raise ApiPostError(json.dumps({"httpStatus": 400, "message": "Api post error."}))
    
    logger.info("Execution complete!")
    event["start_from"] = stop_record
    if(stop_record != len(records)):
        logger.info("In progress")
        event["status"] = "InProgress"
    else:
        logger.info("completed!")
        event["status"] = "Completed"
        set_timestamp(timestamp_param_name, dt.now(tz).strftime(fmt))
    return event

def initial_execution(param_name,bucket,key):
    time = get_timestamp(param_name)
    query = 'SELECT new_global_name,bill_to,bill_to_name, care_of_filter, care_of_name, company, customer_type, source_system,subsidiary_consolidation, id FROM public.global_cust_name WHERE (load_create_date >= \''+time+'\' OR load_update_date >= \''+time+'\')'
    queryData = execute_db_query(query)
    s3Data = s3UploadObject(queryData,'/tmp/global_customers.txt',bucket,key)
    return queryData
    
def convert_records(data):
    try:
        record = {}
        record["unique_id"] = data[9]
        record["customer_name"] = data[0]
        record["bill_to"] = data[1]
        record["bill_to_name"] = data[2]
        record["care_of_filter"] = data[3]
        record["care_of_name"] = data[4]
        record["company"] = data[5]
        record["customer_type"] = data[6]
        record["global_name_match"] = str(data[7])+"-"+str(data[1])
        record["source_system"] = data[7]
        record["state"] = "--"
        record["subsidiary_consolidation"] = data[8]
        return record
    except Exception as e:
        logging.exception("RecordConversionError: {}".format(e))
        raise RecordConversionError(json.dumps({"httpStatus": 400, "message": "Record conversion error."}))

def sns_notify(sub, msg, sns_topic_arn):
    response = sns.publish(
    TopicArn = sns_topic_arn,
    Subject= sub,
    Message= msg)
    print(response)

class EnvironmentVariableError(Exception): pass
class GetS3ObjectError(Exception): pass
class InitializationError(Exception): pass
class UpdateFileError(Exception): pass
class GetParameterError(Exception): pass
class RecordConversionError(Exception): pass
class ApiPostError(Exception): pass
class UpdateFileError(Exception): pass