# ==============================================================================
# !/usr/bin/env python3
# -*- coding: utf-8 -*-
# title              : df_lib.py
# description        : This is functions library
# author             : Pragnakalp Techlabs
# email              : letstalk@pragnakalp.com
# website            : https://www.pragnakalp.com
# python_version     : 3.6.8
# ==============================================================================

# Import required external libraries
from restinmagento.resource import Resource
from restinmagento.oauth import OAuth
import re
import pickle
import json

def update_parameters(req, action):
    """ 
    Return Flow indicator, starting page numbers, last searched product (Query text), text response 
    This parameters are useful to handle the pagination and back functionality.
    """

    # Get parameters from webhook request json
    requests = req.get('queryResult').get('outputContexts')
    platform = req.get('originalDetectIntentRequest').get('source')
    if platform == 'facebook':
        userID = req.get('originalDetectIntentRequest').get('payload').get('data').get('sender').get('id')
    elif platform == 'google':
        userID = req.get('originalDetectIntentRequest').get('payload').get('user').get('userStorage')

    # Read parameters from the output context to control the flow and pagination functionality
    for m in requests:
        name = m.get("name")

        if action == "Back":
            if name[-4:] == "back":
                if platform == "google":
                    storage_location = "./google_storage_data/"
                elif platform == "facebook":
                    storage_location = "./facebook_storage_data/"
                with open(storage_location+userID+".json", 'r') as file:
                    am = json.load(file)[-1][-1]
                # am = m.get('parameters').get('parameter')[-1][-1]
                for m in am:
                    name = m.get("name")
                    if name[-10:] == "pagination":
                        flow_indicator = m.get("parameters").get("page_start")[0]
                        start_point_flow = m.get("parameters").get("page_start")[1]
                        start_point_browse = m.get("parameters").get("page_start")[2]
                        start_point_search = m.get("parameters").get("page_start")[3]
                        search_product_name = m.get("parameters").get("page_start")[4]
                        text_response = m.get("parameters").get("page_start")[5]
                        last_num_of_product = m.get("parameters").get("page_start")[6]
        else:
            if name[-10:] == "pagination":
                flow_indicator = m.get("parameters").get("page_start")[0]
                start_point_flow = m.get("parameters").get("page_start")[1]
                start_point_browse = m.get("parameters").get("page_start")[2]
                start_point_search = m.get("parameters").get("page_start")[3]
                search_product_name = m.get("parameters").get("page_start")[4]
                text_response = m.get("parameters").get("page_start")[5]
                last_num_of_product = m.get("parameters").get("page_start")[6]

    try:
        return flow_indicator, start_point_flow, start_point_browse, start_point_search, search_product_name, text_response, last_num_of_product, action
    except:
        flow_indicator = 0
        start_point_flow = 0
        start_point_browse = 0
        start_point_search = 0
        search_product_name = None
        text_response = " "
        last_num_of_product = 0
        action = "input.welcome"
        return flow_indicator, start_point_flow, start_point_browse, start_point_search, search_product_name, text_response, last_num_of_product, action

def cleanhtml(raw_html):
    """ Return text without any html tags """

    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext



