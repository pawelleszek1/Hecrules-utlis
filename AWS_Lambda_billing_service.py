from __future__ import division
import json
import boto3
import os
import requests
from requests.exceptions import HTTPError
#import logging
#logger = logging.getLogger()
#logger.setLevel(logging.INFO)

#Constants
MAGIC_NUMBER = 0.85 #15% discount for RPO
# SOC ratecard for services provided to DLA Piper
weekend_work_rate_eur = 4665 # weekend work cost is static - always 4665 EUR/month
weekdays_full_time_rate_gbp = 129.2
weekdays_full_time_rate_eur = 187.85
weekdays_full_time_aus_rate_gbp = 113

#Function for getting fx rates from NBP API
def get_rates_of_currency(currency,day):
    try:
        # We use NBP API (table A)
        url = f"http://api.nbp.pl/api/exchangerates/rates/A/{currency}/{day}/"
        response = requests.get(url)
    except HTTPError as http_error:
        print(f'HTTP error: {http_error}')
    except Exception as e:
        print(f'Other exception: {e}')
    else:
        if response.status_code == 200:
            return json.dumps(
                response.json(),
                indent=4,
                sort_keys=True), response.json()

#Function for sending SNS message
def send_sns(message, subject):
    client = boto3.client("sns")
    topic_arn = os.environ["SNS_ARN"]
    client.publish(
        TopicArn=topic_arn, Message=message, Subject=subject)

#main function
def lambda_handler(event, context):
   weekdays_full_time_md = event['wd_ft_md']
   weekdays_full_time_aus_md = event['wd_ft_aus_md']
   fx_date = event['fx_day']

#Let's consume JSON from API as a string
   json_line, GBP = get_rates_of_currency("GBP", fx_date)
   gbp_pln_fx = GBP["rates"][0]["mid"]

   json_line, EUR = get_rates_of_currency("EUR", fx_date)
   eur_pln_fx = EUR["rates"][0]["mid"]

#Let's calculate all values 
#calculate monthly weekend charges:
   weekend_work_cost_pln = weekend_work_rate_eur * eur_pln_fx
   weekend_work_cost_gbp = weekend_work_cost_pln / gbp_pln_fx * MAGIC_NUMBER
   
#calculate weekday full time
   weekday_work_cost_gbp = weekdays_full_time_md * weekdays_full_time_rate_gbp
   weekday_work_cost_pln = weekdays_full_time_md * weekdays_full_time_rate_eur * eur_pln_fx
    
#calculate AUS backfill full time
   weekday_aus_work_cost_pln = weekdays_full_time_aus_md * weekdays_full_time_aus_rate_gbp * gbp_pln_fx
   weekday_aus_work_cost_gbp = weekday_aus_work_cost_pln / gbp_pln_fx * MAGIC_NUMBER
   
#Nice numbers formatting for output
   wwc_pln = "{0:.2f}".format(weekend_work_cost_pln)
   wwc_gbp = "{0:.2f}".format(weekend_work_cost_gbp)
   wwwc_gbp = "{0:.2f}".format(weekday_work_cost_gbp)
   wwft_pln = "{0:.2f}".format(weekday_work_cost_pln)
   wwftaus_pln = "{0:.2f}".format(weekday_aus_work_cost_pln)
   wwftaus_gbp = "{0:.2f}".format(weekday_aus_work_cost_gbp)

#Let's format e-mail message
   sns_email_body = "This is your SOC DLA Piper billing data." + "\n" \
   + "All values are calculated using NBP avg. exchange rates for: " + fx_date + "\n\n" \
   + "Weekend work cost PLN = " + wwc_pln + "\n" \
   + "Weekend work cost GBP = " + wwc_gbp + "\n\n" \
   + "Weekday work full time cost GBP = " + wwwc_gbp + "\n" \
   + "Weekday work full time cost PLN = " + wwft_pln + "\n\n" \
   + "Weekday work full time AUS backfill cost PLN = " + wwftaus_pln + "\n" \
   + "Weekday work full time AUS backfill cost GBP = " + wwftaus_gbp + "\n\n" \
   + "That's all! Have a good day!" + "\n" \
   + "Your highly sophisticated AWS Lambda function..."
   
   subject = "SOC DLA Piper monthly billing. Invoice values"
   send_sns(sns_email_body, subject)

#main function returns values below (for API calls)
   return {
       "Weekend work cost PLN = ": wwc_pln,
       "Weekend work cost GBP = ": wwc_gbp,
       "Weekday work full time cost GBP = ": wwwc_gbp,
       "Weekday work full time cost PLN = ": wwft_pln,
       "Weekday work full time AUS backfill cost PLN = ": wwftaus_pln,
       "Weekday work full time AUS backfill cost GBP = ": wwftaus_gbp
   }
