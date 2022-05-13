
from datetime import datetime

"""
    Update time variables for logging
"""
def get_date_and_time():
    # get current date as datetime object
    date_time = datetime.now()
    # convert date (yyyy-mm-dd) to string
    date = str(date_time).split(' ')[0]
    # convert time (hh:mm) to string
    current_time = ":".join(str(date_time).split(' ')[1].split(".")[0].split(":")[:-1])
    
    return date ,current_time

