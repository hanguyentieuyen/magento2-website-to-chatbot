# ==============================================================================
# !/usr/bin/env python3
# -*- coding: utf-8 -*-
# title              : views.py
# description        : This is the webhook code for the dialogflow response for the magento website
# author             : Pragnakalp Techlabs
# email              : letstalk@pragnakalp.com
# website            : https://www.pragnakalp.com
# python_version     : 3.6.8
# ==============================================================================

# Import required libraries
import json
import importlib
from variables import client_key, client_secret, resource_owner_key, resource_owner_secret, base_url, store_name, app_name
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from restinmagento.oauth import OAuth # <-- install restinmagento 
from restinmagento.resource import Resource
from library.facebook_template_lib import FacebookTemplate # <--
from library.df_response_lib import actions_on_google_response, facebook_response, fulfillment_response
from requests_oauthlib import OAuth1
import requests
import os

df_lib = importlib.import_module(app_name+".df_lib")
df_facebook = importlib.import_module(app_name+".df_facebook")

def home(request):
    """ Return http response """
    return HttpResponse('Hello World!')

@csrf_exempt
def webhook(request):
    """ Return webhook response to DialogFlow """

    # Initialization of variables
    length_product_sku = 2**100
    length = 2**100
    total_product_found = 2**100
    
    no_update = 0
    no_suggestion = 0
    one_product = 0
    
    # Define the size of the page for the pagination in the list response
    flow_1_page_size = 10
    flow_2_page_size = 10
    flow_3_page_size = 10

    # Read a request object from the dialogFlow webhook request
    req = json.loads(request.body.decode('utf-8'))

    # Authentication for Magento API excess
    oauth = OAuth(client_key=client_key,
        client_secret=client_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret)

    # Authentication for Magento API excess using OAuth1
    oauth1 = OAuth1(client_key=client_key,
        client_secret=client_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret)

    # Extract the symbol of the currency used in the store
    currency_resource  = Resource(base_url+'rest/V1/directory/currency', oauth)
    currency_dict = currency_resource.get()
    currency_json = currency_dict.json()
    currency_symbol = currency_json["base_currency_symbol"]

    # Extract product categories detail using magento API
    category_resource  = Resource(base_url+'rest/V1/categories/', oauth)
    category_dict = category_resource.get()
    category_json = category_dict.json()

    # Extracting main categories' name and id
    main_categories_name = []
    main_categories_id = []

    for c in category_json['children_data']:
        if c['is_active'] == True and (c['product_count'] != 0 or c['children_data'] != []):
            main_categories_name.append(c['name'])
            main_categories_id.append(c['id'])

    # Extracting subcategories' name and id
    subcategories_names = []
    subcategories_ids = []
    for i in range(len(main_categories_id)):
        name = []
        id = []
        for c in category_json['children_data']:
            if c['name'] == main_categories_name[i]:
                for f in c['children_data']:
                    if f['is_active'] == True:
                        name.append(f['name'])
                        id.append(f['id'])

        subcategories_names.append(name)
        subcategories_ids.append(id)

    # Read action of the intent from the webhook request
    action = req.get('queryResult').get('action')

    # Redirect to product list if there is no subcategories available for the given category
    redirect = 0
    if action == 'sub_category':
        parameters = req.get('queryResult').get('parameters').get("category_number")
        if parameters == "":
            redirect = 1
            outputContexts = req.get('queryResult').get('outputContexts')
            for m in outputContexts:
                name = m.get("name")
                word = "one_item_list"
                if name[-len(word):] == word:
                    parameters = int(float(m.get('parameters').get('key_value')))
        else:
            parameters = int(float(parameters)) #get parameters from json
            for i in range(len(main_categories_id)):
                for c in category_json['children_data']:
                    if c['is_active'] == True and c['id'] == parameters:
                        if c['children_data'] == []:
                            action = 'product_list'
                            redirect = 1
    elif action == 'product_list':
        if redirect != 1:
            try:
                parameters = req.get('queryResult').get('parameters').get("category_number")
                if parameters == "":
                    redirect = 1
                    outputContexts = req.get('queryResult').get('outputContexts')
                    for m in outputContexts:
                        name = m.get("name")
                        word = "one_item_list"
                        if name[-len(word):] == word:
                            parameters = int(float(m.get('parameters').get('key_value')))
                else:
                    parameters = int(float(req.get('queryResult').get('parameters').get("category_number"))) #get parameters from json
            except:
                redirect = 1
                action = "product_detail"

    # Initialize or update parameters from the last response for the pagination
    if action == 'input.welcome':
        flow_indicator = 0
        start_point_flow = 0
        start_point_browse = 0
        start_point_search = 0
        search_product_name = None
        last_num_of_product = 0
    else:
        flow_indicator, start_point_flow, start_point_browse, start_point_search, search_product_name, text_response, last_num_of_product, action    = df_lib.update_parameters(req, action)
    
    # Get the platform of the chatbot
    platform = req.get('originalDetectIntentRequest').get('source')

    # Get the class objects for the appropiate platform
    if platform == 'facebook':
        fb = facebook_response()
        fb_t = FacebookTemplate()
        userID = req.get('originalDetectIntentRequest').get('payload').get('data').get('sender').get('id')

    elif platform == 'google' or 'None':
        aog = actions_on_google_response()
        if platform == 'google':
            userID = req.get('originalDetectIntentRequest').get('payload').get('user').get('userStorage')

    # Default welcome intent response   
    if action == "input.welcome":
        text_response = "Welcome to " + store_name +"."
        suggestion_text_fb = "How would you like to explore?"
        if platform == "google":
            text_response += "  \n" + suggestion_text_fb
        suggestions = ["Show categories", "Search product", "Browse all product"]

    # Main categories of the store - selection list response
    elif action == 'category_names':

        flow_indicator = 1
        text_response = 'Select your category here.'
        list_elements = []

        # lopp over all categories
        for a in range(len(main_categories_name)):
            image_url = ""
            if  platform == 'facebook':
                fb_t_e = df_facebook.genric_list_fesponse(main_categories_name,"", main_categories_id, image_url = image_url, index =  a)
                fb_t.add_element(fb_t_e)

            elif platform == 'google' or 'None':
                # if there is only 1 category, then list respose won't be work, to solve that we are giving card response 
                if len(main_categories_name) == 1:
                    text_response = "Say 'Subcategory' to check more subcategory of "+ main_categories_name[a] +"."
                    suggestions = ["Subcategory", "Back"]
                    one_product = 1
                    key = main_categories_id[a]
                    aog_sc = aog.basic_card(main_categories_name[a], subtitle="check subcategories of "+str(main_categories_name[a]), formattedText="", image=[image_url, "Sample_image"])
                else:
                    list_elements.append([main_categories_name[a], "check subcategories of "+str(main_categories_name[a]), [main_categories_id[a], [main_categories_name[a]+str(1), main_categories_name[a]+str(2)]],["", 'image_discription']])

        if platform == 'facebook':
            suggestion_text_fb = "Say BACK to browse previous response."
            fb_sc = fb.custom_payload(fb_t.get_payload())
        elif (platform == 'google' or 'None') and len(main_categories_name) > 1:
            list_title = "Categories"
            aog_sc = aog.list_select(list_title, list_elements)

    # Subcategories webhook selection list response
    elif action == 'sub_category':

        search_product_name = req.get('queryResult').get('parameters').get("category_number") #get parameters from json
        if search_product_name == "":
            redirect = 1
            outputContexts = req.get('queryResult').get('outputContexts')
            for m in outputContexts:
                name = m.get("name")
                word = "one_item_list"
                if name[-len(word):] == word:
                    search_product_name = int(float(m.get('parameters').get('key_value')))
        else:
            search_product_name = int(float(search_product_name))

        list_elements = []

        # loop over all categories
        found_subcategory = 0
        for i in range(len(main_categories_id)):
            subcategories_name = subcategories_names[i]
            subcategories_id = subcategories_ids[i]

            if search_product_name == main_categories_id[i]:
                found_subcategory = 1
                text_response = "Select subcategory for " + main_categories_name[i]+"."
                
                # loop over all subcategories
                for a in range(len(subcategories_name)):
                    image_url = ""
                    if platform == 'facebook':
                        fb_t_e = df_facebook.genric_list_fesponse(subcategories_name, "", subcategories_id, index = a)
                        fb_t.add_element(fb_t_e)
                    elif platform == 'google' or 'None':
                        # if there is only 1 subcategory, then list respose won't be work, to solve that we are giving card response
                        if len(subcategories_name) == 1:
                            text_response = "Reply 'Product list' to check more products of "+ subcategories_name[a] +"."
                            suggestions = ["Product list", "Back"]
                            one_product = 1
                            key = subcategories_id[a]
                            aog_sc = aog.basic_card(subcategories_name[a], subtitle="check products of "+str(subcategories_name[a]), formattedText="", image=[image_url, "Sample_image"])
                        else:
                            list_elements.append([subcategories_name[a], "check products of "+str(subcategories_name[a]), [subcategories_id[a], [subcategories_name[a]+str(1), subcategories_name[a]+str(2)]],[image_url, 'image_discription']])
        if found_subcategory == 0:
            no_update = 1

        if platform == 'facebook':
            suggestion_text_fb = "Say BACK to browse previous response."
            fb_sc = fb.custom_payload(fb_t.get_payload())
        elif platform == 'google' or 'None':
            list_title = 'Sub-categories'
            if len(list_elements) > 1:
                aog_sc = aog.list_select(list_title, list_elements)
            
    # Main categories webhook selection list response
    elif action == 'product_list':

        flow_indicator = 1
        text_response = "Which one you would like to buy? Select to choose your's.:"

        # if exctracting product list of redirect main category (no subcategories available) then use parameter value exctracted above
        if redirect != 1:
            parameters = int(float(req.get('queryResult').get('parameters').get("category_number"))) #get parameters from json

        search_product_name = parameters
        
        # Extracting sku of the products of given category id using Magento API
        source_path = base_url+'rest/V1/categories/'+str(int(parameters))+'/products'
        product_sku_resource  = Resource(source_path, oauth)
        product_sku_dict = product_sku_resource.get()
        products_sku_json = product_sku_dict.json()
        product_sku = []
        
        for a in range(len(products_sku_json)):
            product_sku.append(products_sku_json[a]['sku'])

        products = []
        length_product_sku = len(product_sku)        
        list_elements = []
        no_product = 0

        i = 0
        request_url = base_url+"rest/V1/products"
        params = dict()
        for a in range(length_product_sku):

            if start_point_flow < 0:
                start_point_flow = 0

            if a >= start_point_flow and a < start_point_flow + flow_1_page_size:
                product_sku[a] = product_sku[a].replace(" ", "")
                params["searchCriteria[filter_groups][0][filters]["+str(i)+"][field]"] = "sku"
                params["searchCriteria[filter_groups][0][filters]["+str(i)+"][value]"] = str(product_sku[a])
                params["searchCriteria[filter_groups][0][filters]["+str(i)+"][condition_type]"] = "eq"
                i += 1
            elif a >= start_point_flow + flow_1_page_size:
                break

        params["searchCriteria[filter_groups][1][filters][0][field]"] = "type_id"
        params["searchCriteria[filter_groups][1][filters][0][value]"] = "configurable"
        params["searchCriteria[filter_groups][1][filters][0][condition_type]"] = "eq"
        params["searchCriteria[filter_groups][1][filters][1][field]"] = "type_id"
        params["searchCriteria[filter_groups][1][filters][1][value]"] = "simple"
        params["searchCriteria[filter_groups][1][filters][1][condition_type]"] = "eq"

        product_dict = requests.get(url = request_url, params = params, auth = oauth1)
        product_list_json = product_dict.json()
        products = product_list_json["items"]

        # Reading features of the product details (name, price, image url)
        # all try and except sentences used to manage the SKU string format error
        for b in products:
            try:
                product_name = b['name']
            except:
                try:
                    product_name = b['items'][0]['name']
                except:
                    no_product = 1
                    continue

            try:
                product_sku = b['sku']
            except:
                try:
                    product_sku = b['items'][0]['sku']
                except:
                    pass

            try:
                product_type = b['type_id']
            except:
                try:
                    product_type = b['items'][0]['type_id']
                except:
                    pass

            prices = []

            if product_type == "configurable":
                children_product_path = str(base_url+"rest/V1/configurable-products/"+str(product_sku)+"/children")
                children_product_resource = Resource(children_product_path, oauth)
                children_product_dict = children_product_resource.get()
                children_product_json = children_product_dict.json()
                for child in children_product_json:
                    prices.append(child['price'])
                product_price = min(prices)
            else:
                try:
                    product_price = b['price']
                except:
                    try:
                        product_price = b['items'][0]['price']
                    except:
                        pass

            if product_type == "configurable":
                try:
                    configuration_options = b['extension_attributes']['configurable_product_options']
                except:
                    try:
                        configuration_options = b['items'][0]['extension_attributes']['configurable_product_options']
                    except:
                        pass
            product_image = ""
            image_url = ""
            special_price = " "    
            try:
                for c in b['custom_attributes']:
                    if c['attribute_code'] == 'image':
                        product_image = c['value']
                        image_url = base_url+ 'media/catalog/product/' + product_image
                    elif c['attribute_code'] == 'special_price':
                        special_price = c['value']  
            except:
                try:
                    for c in b['items'][0]['custom_attributes']:
                        if c['attribute_code'] == 'image':
                            product_image = c['value']
                            image_url = base_url+ 'media/catalog/product/' + product_image
                        elif c['attribute_code'] == 'special_price':
                            special_price = c['value']
                except:
                    pass
            if product_type == "configurable":
                price_text = "Price starts from: "+ currency_symbol
            else:
                price_text = "Price: "+ currency_symbol
            
            if no_product == 1:
                continue
            if platform == 'facebook':
                try:
                    fb_t_e = df_facebook.genric_list_fesponse(product_name,price_text+"{0:.2f}".format(float(special_price))+ "\nRegular Price: "+currency_symbol+str(product_price), str(product_sku), image_url)
                except:
                    try:
                        fb_t_e = df_facebook.genric_list_fesponse(product_name,price_text+str(product_price), str(product_sku), image_url)
                    except:
                        try:
                            fb_t_e = df_facebook.genric_list_fesponse(product_name," ", str(product_sku), image_url)
                        except:
                            fb_t_e = df_facebook.genric_list_fesponse(product_name," ", str(product_sku))
                fb_t.add_element(fb_t_e)
            
            elif platform == 'google' or 'None':

                # if only one product the list response won't be work, to solve that we are uuing card response
                # all try - except are to solve the unsufficient data avilable of the products to display
                if length_product_sku - start_point_flow == 1:
                    text_response = "Reply 'Product detail' to get more details of "+ product_name +"."
                    suggestions = ["Product detail", "Back"]
                    one_product = 1
                    key = product_sku
                    try:
                        aog_sc = aog.basic_card(product_name, subtitle=price_text+ "{0:.2f}".format(float(special_price))+ "\nRegular Price: "+currency_symbol+str(product_price), image=[image_url, "Sample_image"])  
                    except:
                        try:
                            aog_sc = aog.basic_card(product_name, subtitle=price_text+str(product_price), image=[image_url, "Sample_image"])
                        except:
                            try:
                                aog_sc = aog.basic_card(product_name, subtitle=" "+str(product_price), image=[image_url, "Sample_image"])
                            except:
                                aog_sc = aog.basic_card(product_name, subtitle=" "+str(product_price))
                else:
                    try:
                        list_elements.append([product_name,price_text+"{0:.2f}".format(float(special_price))+ "\nRegular Price: "+currency_symbol+str(product_price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])
                    except:
                        try:
                            list_elements.append([product_name, price_text+str(product_price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])
                        except:
                            list_elements.append([product_name, " ", [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])

        if platform == 'facebook':
            fb_sc = fb.custom_payload(fb_t.get_payload())
        elif platform == 'google' or 'None':
            list_title = 'products'
            if length_product_sku - start_point_flow > 1:
               aog_sc = aog.list_select(list_title, list_elements)

    # Browse Product Response
    elif action == "browse_product":
        flow_indicator = 2
        text_response = "Which one you would like to buy? Select to choose your's."
        
        # Extracting products from the all the categories to browse the products
        product_source_path = str(base_url+"rest/V1/products?searchCriteria[pageSize]="+str(flow_2_page_size)+"&searchCriteria[currentPage]="+str(int(start_point_browse/flow_2_page_size)+1)+"&searchCriteria[filter_groups][0][filters][0][field]=visibility&searchCriteria[filter_groups][0][filters][0][value]=1&searchCriteria[filter_groups][0][filters][0][condition_type]=neq&searchCriteria[filter_groups][1][filters][0][field]=type_id&searchCriteria[filter_groups][1][filters][0][value]=simple&searchCriteria[filter_groups][1][filters][0][condition_type]=eq&searchCriteria[filter_groups][1][filters][1][field]=type_id&searchCriteria[filter_groups][1][filters][1][value]=configurable&searchCriteria[filter_groups][1][filters][1][condition_type]=like")
        resource_product = Resource(product_source_path, oauth)
        product_list_dict = resource_product.get()
        product_list_json = product_list_dict.json()
        p = product_list_json.get("items")

        # Number of total products
        length = product_list_json.get("total_count")

        # Number of products in one page
        length_product_sku_flow_2 = len(p)
        
        # Reading features of the product(name, price, sku, image url) and appending in the list response
        list_elements = []

        # loop over all products of the page, extract the features of the product and prepare response
        for n in range(length_product_sku_flow_2):
            
            product_name = p[n].get("name")
            product_sku = p[n].get("sku")
            product_type = p[n].get("type_id")
            if product_type == "configurable":
                price = "As per options"
            else:
                price = p[n].get('price') # <--
            
            special_price = " "
            product_image = ""
            image_url = ""
            product_description = " "

            for c in p[n]['custom_attributes']: # <--
                if c['attribute_code'] == "description": # <--
                    product_description = df_lib.cleanhtml(c['value']) # <--
                elif c['attribute_code'] == 'image': # <--
                    product_image = c['value'] # <--
                    image_url = base_url+ 'pub/media/catalog/product' + product_image
                elif c['attribute_code'] == "special_price": # <--
                    special_price = c['value'] # <--

            if product_type == "configurable":
                price_text = "Price starts from: "
            else:
                price_text = "Price: "+currency_symbol

            if platform == "facebook":
                if special_price != None and special_price != " ":
                    fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text+"{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(price), str(product_sku), image_url)
                else:
                    if price != None: # <--
                        fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text+ str(price), str(product_sku), image_url)
                    else:
                        fb_t_e = df_facebook.genric_list_fesponse(product_name," ", str(product_sku), image_url)                        
                fb_t.add_element(fb_t_e)

            elif platform == 'google' or 'None':
                if length_product_sku_flow_2 == 1:
                    text_response = "Reply 'Product detail' to get more details of "+ product_name +"."
                    suggestions = ["Product detail", "Back"]
                    one_product = 1
                    key = product_sku
                    if special_price != None:
                        aog_sc = aog.basic_card(product_name, subtitle=  price_text+"{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(price), image=[image_url, "Sample_image"])
                    else:
                        if price != None: # <--
                            aog_sc = aog.basic_card(product_name, subtitle=  price_text+ str(price), image=[image_url, "Sample_image"])  
                        else:
                            aog_sc = aog.basic_card(product_name, subtitle= " ", image=[image_url, "Sample_image"])
                else:
                    if special_price != None:
                        list_elements.append([product_name,  price_text+"{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']]) # <--
                    else:
                        if price != None: # <--
                            list_elements.append([product_name,  price_text+ str(price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])         # <--
                        else:
                            list_elements.append([product_name, " ", [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])         # <--
        
        if platform == 'facebook':
            fb_sc = fb.custom_payload(fb_t.get_payload())
        elif platform == 'google' or 'None':
            list_title = 'Products list'
            if length_product_sku_flow_2 != 1:
                aog_sc = aog.list_select(list_title, list_elements)

    # Response when asked for "search product"
    elif action == "ask_search_product":
        text_response = "Please enter product name."
        suggestion_text_fb = "Say BACK to browse previous response."

    # Response of the searched product
    elif action == "search_product":
        flow_indicator = 3

        search_product_name = req.get('queryResult').get('parameters').get("product_name") #get parameters from json
        
        # Exctracting the search product result using the Magento API
        search_product_path = str(base_url+"rest/V1/products?searchCriteria[filter_groups][0][filters][0][field]=name&searchCriteria[filter_groups][0][filters][0][value]=%"+ str(search_product_name) +"%&searchCriteria[filter_groups][0][filters][0][condition_type]=like&searchCriteria[filter_groups][1][filters][0][field]=visibility&searchCriteria[filter_groups][1][filters][0][value]=1&searchCriteria[filter_groups][1][filters][0][condition_type]=neq&searchCriteria[filter_groups][2][filters][0][field]=type_id& searchCriteria[filter_groups][2][filters][0][value]=simple&searchCriteria[filter_groups][2][filters][0][condition_type]=eq&searchCriteria[filter_groups][2][filters][1][field]=type_id&searchCriteria[filter_groups][2][filters][1][value]=configurable&searchCriteria[filter_groups][2][filters][1][condition_type]=like")
        search_product_resource = Resource(search_product_path, oauth)
        search_product_dict = search_product_resource.get()
        search_product_json = search_product_dict.json()

        # Total searched products
        total_product_found = search_product_json.get("total_count")
        if int(total_product_found) >= 1:
            no_product_found = 0
            # Simple response text
            text_response = str(total_product_found) + " results found for the " + search_product_name

            # Reading the features of the product (name, image url, url key, product description)
            a = 0        
            list_elements = []
            for p in search_product_json.get("items"):
                
                if start_point_search < 0:
                    start_point_search = 0
                
                if a >= start_point_search and a < start_point_search + flow_3_page_size:
                    product_name = p.get("name")
                    product_sku = p.get("sku")
                    product_type = p.get("type_id")
                    if product_type == "configurable":
                        price = "As per options"
                    else:
                        price = p.get('price')

                    product_description = " "
                    product_image = ""
                    special_price = " "
                    image_url = ""
                    for c in p['custom_attributes']:
                        try:
                            if c['attribute_code'] == "description":
                                product_description = df_lib.cleanhtml(c['value'])
                            elif c['attribute_code'] == 'image':
                                product_image = c['value']
                            elif c['attribute_code'] == "special_price":
                                special_price = c['value']
                            image_url = base_url+ 'pub/media/catalog/product' + product_image
                        except:
                            pass

                    if product_type == "configurable":
                        price_text = "Price: "
                    else:
                        price_text = "Price: "+currency_symbol

                    if platform == 'facebook':
                        try:
                            fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text + "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(product_price), str(product_sku), image_url)
                        except:
                            try:
                                fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text + str(price), str(product_sku), image_url)
                            except:
                                fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text + str(price), str(product_sku))
                        fb_t.add_element(fb_t_e)
                    elif platform == 'google' or 'None':
                        text_response = "Reply 'Product detail' to get more details of "+ product_name +"."
                        suggestions = ["Product detail", "Back"]
                        one_product = 1
                        key = product_sku
                        if total_product_found - start_point_search == 1:
                            try:
                                aog_sc = aog.basic_card(product_name, subtitle= price_text + "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(product_price), image=[image_url, "Sample_image"])                    
                            except:
                                try:
                                    aog_sc = aog.basic_card(product_name, subtitle= price_text + str(price), image=[image_url, "Sample_image"])
                                except:
                                    aog_sc = aog.basic_card(product_name, subtitle= price_text + str(price))
                        else:
                            try:
                                list_elements.append([product_name, price_text + "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])
                            except:
                                try:
                                    list_elements.append([product_name, price_text + str(price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])
                                except:
                                    list_elements.append([product_name, price_text + str(price), [product_sku, [product_name+str(1), product_name+str(2)]]])
                
                elif a >= start_point_search + flow_3_page_size:
                    break
                a += 1
            last_num_of_product = a

            if platform == 'facebook':
                fb_sc = fb.custom_payload(fb_t.get_payload())
            elif platform == 'google' or 'None':
                # For 1 result card response, more than 1 result list response with pagination
                if total_product_found == 0:
                    text = "There is no product with name "+str(search_product_name)
                    aog_sc = aog.simple_response([[text, text, False]])
                else:
                    list_title = 'Searched Products'
                    if total_product_found - start_point_search != 1:
                        aog_sc = aog.list_select(list_title, list_elements)
        else:
            no_product_found = 1
            text_response = "No product found with the name " + search_product_name + "  \nPlease try with another keyword"
            
    # Next and Previous page response in the pagination functionality
    elif action == "next" or action == "previous":

        # update the starting points of the pagination for the different flow according to "next" or "previous"
        if flow_indicator == 1:
            if action == "next":
                start_point_flow += flow_1_page_size
            elif action == "previous":
                start_point_flow -= flow_1_page_size

        elif flow_indicator == 2:
            if action == "next":
                start_point_browse += flow_2_page_size
            elif action == "previous":
                start_point_browse -= flow_2_page_size

        elif flow_indicator == 3:
            if action == "next":
                start_point_search += flow_3_page_size
            elif action == "previous":
                start_point_search -= flow_3_page_size


        # Next intent response for the regular product display flow 
        if flow_indicator == 1:

            # Extracting sku of products of given category id using Magento
            source_path = base_url+'rest/V1/categories/'+str(int(search_product_name))+'/products'
            resource_product_sku  = Resource(source_path, oauth)
            product_sku_dict = resource_product_sku.get()
            products_sku_json = product_sku_dict.json()
            product_sku = []
            for a in range(len(products_sku_json)):
                product_sku.append(products_sku_json[a]['sku'])

            # Magento - Gethering product details in list format
            products = []

            # Managing the pagination flow and page size
            length_product_sku = len(product_sku)

            list_elements = []
            no_product = 0
            i = 0
            request_url = base_url+"rest/V1/products"
            params = dict()
            for a in range(length_product_sku):

                if start_point_flow < 0:
                    start_point_flow = 0

                if a >= start_point_flow and a < start_point_flow + flow_1_page_size:
                    product_sku[a] = product_sku[a].replace(" ", "")
                    params["searchCriteria[filter_groups][0][filters]["+str(i)+"][field]"] = "sku"
                    params["searchCriteria[filter_groups][0][filters]["+str(i)+"][value]"] = str(product_sku[a])
                    params["searchCriteria[filter_groups][0][filters]["+str(i)+"][condition_type]"] = "eq"
                    i += 1
                elif a >= start_point_flow + flow_1_page_size:
                    break

            params["searchCriteria[filter_groups][1][filters][0][field]"] = "type_id"
            params["searchCriteria[filter_groups][1][filters][0][value]"] = "configurable"
            params["searchCriteria[filter_groups][1][filters][0][condition_type]"] = "eq"
            params["searchCriteria[filter_groups][1][filters][1][field]"] = "type_id"
            params["searchCriteria[filter_groups][1][filters][1][value]"] = "simple"
            params["searchCriteria[filter_groups][1][filters][1][condition_type]"] = "eq"

            product_dict = requests.get(url = request_url, params = params, auth = oauth1)
            product_list_json = product_dict.json()
            products = product_list_json["items"]

            # Reading features of the product details (name, price, image url)
            # all try and except sentences used to manage the SKU string format error
            for b in products:
                try:
                    product_name = b['name']
                except:
                    try:
                        product_name = b['items'][0]['name']
                    except:
                        no_product = 1
                        continue

                try:
                    product_sku = b['sku']
                except:
                    try:
                        product_sku = b['items'][0]['sku']
                    except:
                        pass

                try:
                    product_type = b['type_id']
                except:
                    try:
                        product_type = b['items'][0]['type_id']
                    except:
                        pass
                prices = []

                if product_type == "configurable":
                    children_product_path = str(base_url+"rest/V1/configurable-products/"+str(product_sku)+"/children")
                    children_product_resource = Resource(children_product_path, oauth)
                    children_product_dict = children_product_resource.get()
                    children_product_json = children_product_dict.json()
                    for child in children_product_json:
                        prices.append(child['price'])
                    product_price = min(prices)
                else:
                    try:
                        product_price = b['price']
                    except:
                        try:
                            product_price = b['items'][0]['price']
                        except:
                            pass

                if product_type == "configurable":
                    try:
                        configuration_options = b['extension_attributes']['configurable_product_options']
                    except:
                        try:
                            configuration_options = b['items'][0]['extension_attributes']['configurable_product_options']
                        except:
                            pass
                product_image = ""
                special_price = " "
                try:
                    for c in b['custom_attributes']:
                        if c['attribute_code'] == 'image':
                            product_image = c['value']
                            image_url = base_url+ 'media/catalog/product/' + product_image
                        elif c['attribute_code'] == 'special_price':
                            special_price = c['value']  
                except:
                    try:
                        for c in b['items'][0]['custom_attributes']:
                            if c['attribute_code'] == 'image':
                                product_image = c['value']
                                image_url = base_url+ 'media/catalog/product/' + product_image
                            elif c['attribute_code'] == 'special_price':
                                special_price = c['value']
                    except:
                        pass

                if product_type == "configurable":
                    price_text = "Price starts from: "+currency_symbol
                else:
                    price_text = "Price: "+currency_symbol
                
                if no_product == 1:
                    continue
                if platform == 'facebook':
                    try:
                        fb_t_e = df_facebook.genric_list_fesponse(product_name,price_text+"{0:.2f}".format(float(special_price))+ "\nRegular Price: "+currency_symbol+str(product_price), str(product_sku), image_url)
                    except:
                        try:
                            fb_t_e = df_facebook.genric_list_fesponse(product_name,price_text+str(product_price), str(product_sku), image_url)
                        except:
                            try:
                                fb_t_e = df_facebook.genric_list_fesponse(product_name," ", str(product_sku), image_url)
                            except:
                                fb_t_e = df_facebook.genric_list_fesponse(product_name," ", str(product_sku))
                    fb_t.add_element(fb_t_e)
                
                elif platform == 'google' or 'None':

                    # if only one product the list response won't be work, to solve that we are uuing card response
                    # all try - except are to solve the unsufficient data avilable of the products to display
                    if length_product_sku - start_point_flow == 1:
                        text_response = "Reply 'Product detail' to get more details of "+ product_name +"."
                        suggestions = ["Product detail", "Back"]
                        one_product = 1
                        key = product_sku
                        try:
                            aog_sc = aog.basic_card(product_name, subtitle=price_text+ "{0:.2f}".format(float(special_price))+ "\nRegular Price: "+currency_symbol+str(product_price), image=[image_url, "Sample_image"])  
                        except:
                            try:
                                aog_sc = aog.basic_card(product_name, subtitle=price_text+str(product_price), image=[image_url, "Sample_image"])
                            except:
                                try:
                                    aog_sc = aog.basic_card(product_name, subtitle=" "+str(product_price), image=[image_url, "Sample_image"])
                                except:
                                    aog_sc = aog.basic_card(product_name, subtitle=" "+str(product_price))
                    else:
                        try:
                            list_elements.append([product_name,price_text+"{0:.2f}".format(float(special_price))+ "\nRegular Price: "+currency_symbol+str(product_price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])
                        except:
                            try:
                                list_elements.append([product_name, price_text+str(product_price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])
                            except:
                                list_elements.append([product_name, " ", [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])

            if platform == 'facebook':
                fb_sc = fb.custom_payload(fb_t.get_payload())
            elif platform == 'google' or 'None':
                list_title = 'products'
                if length_product_sku - start_point_flow != 1:
                    aog_sc = aog.list_select(list_title, list_elements)

        # Next intent response for the browse product flow
        elif flow_indicator == 2:

            # Exctracting all the products details with the page size 10
            
            product_source_path = str(base_url+"rest/V1/products?searchCriteria[pageSize]="+str(flow_2_page_size)+"&searchCriteria[currentPage]="+str(int(start_point_browse/flow_2_page_size)+1)+"&searchCriteria[filter_groups][0][filters][0][field]=visibility& searchCriteria[filter_groups][0][filters][0][value]=1&searchCriteria[filter_groups][0][filters][0][condition_type]=neq&searchCriteria[filter_groups][1][filters][0][field]=type_id& searchCriteria[filter_groups][1][filters][0][value]=simple&searchCriteria[filter_groups][1][filters][0][condition_type]=eq&searchCriteria[filter_groups][1][filters][1][field]=type_id&searchCriteria[filter_groups][1][filters][1][value]=configurable&searchCriteria[filter_groups][1][filters][1][condition_type]=like")
            resource_product = Resource(product_source_path, oauth)
            product_list_dict = resource_product.get()
            product_list_json = product_list_dict.json()
            p = product_list_json.get("items")
            length = product_list_json.get("total_count")
            length_product_sku_flow_2 = len(p)

            # Reading the features of the product (name, price, sku, image url) 
            list_elements = []
            for n in range(length_product_sku_flow_2):
                product_name = p[n].get("name")
                product_price = p[n].get("price")
                product_sku = p[n].get("sku")
                product_type = p[n].get("type_id")
                if product_type == "configurable":
                    price = "As per options"
                else:
                    price = p[n].get('price') # <--
                product_image = p[n].get("custom_attributes")[0].get("value")
                    
                special_price = " "
                product_description = " "
                product_image = ""
                image_url = ""
                for c in p[n]['custom_attributes']: # <--
                    if c['attribute_code'] == "description": # <--
                        product_description = df_lib.cleanhtml(c['value']) # <--
                    elif c['attribute_code'] == 'image': # <--
                        product_image = c['value'] # <--
                    elif c['attribute_code'] == "special_price": # <--
                        special_price = c['value'] # <--

                image_url = base_url+ 'pub/media/catalog/product' + product_image

                if product_type == "configurable":
                    price_text = "Price starts from: "
                else:
                    price_text = "Price: "+currency_symbol
                
                if platform == 'facebook':
                    if special_price != None:
                        fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text+ "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(price), str(product_sku), image_url)
                    else:
                        if price != None: # <--
                            fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text+ str(price), str(product_sku), image_url)
                        else:
                            fb_t_e = df_facebook.genric_list_fesponse(product_name," ", str(product_sku), image_url)
                    fb_t.add_element(fb_t_e)
                elif platform == 'google' or 'None':
                    if length_product_sku_flow_2 == 1:
                        one_product = 1
                        key = product_sku
                        text_response = "Reply 'Product detail' to get more details of "+ product_name +"."
                        suggestions = ["Product detail", "Back"]
                        if special_price != None:
                            aog_sc = aog.basic_card(product_name, subtitle= price_text+ "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(price), image=[image_url, "Sample_image"])
                        else:
                            if price != None: # <--
                                aog_sc = aog.basic_card(product_name, subtitle= price_text+ str(price), image=[image_url, "Sample_image"])  
                            else:
                                aog_sc = aog.basic_card(product_name, subtitle= " ", image=[image_url, "Sample_image"])
                    else:
                        if special_price != None:
                            list_elements.append([product_name,  price_text+ "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']]) # <--
                        else:
                            if price != None: # <--
                                list_elements.append([product_name,  price_text+ str(price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])         # <--
                            else:
                                list_elements.append([product_name, " ", [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])         # <--

            if platform == 'facebook':
                fb_sc = fb.custom_payload(fb_t.get_payload())
            elif platform == 'google' or 'None':
                list_title = 'Products List'
                if length_product_sku_flow_2 != 1:
                    aog_sc = aog.list_select(list_title, list_elements)

        elif flow_indicator == 3:
            
            # Exctracting the search product result using the Magento API
            search_product_path = str(base_url+"rest/V1/products?searchCriteria[filter_groups][0][filters][0][field]=name&searchCriteria[filter_groups][0][filters][0][value]=%"+ str(search_product_name) +"%&searchCriteria[filter_groups][0][filters][0][condition_type]=like&searchCriteria[filter_groups][1][filters][0][field]=visibility&searchCriteria[filter_groups][1][filters][0][value]=1&searchCriteria[filter_groups][1][filters][0][condition_type]=neq&searchCriteria[filter_groups][2][filters][0][field]=type_id& searchCriteria[filter_groups][2][filters][0][value]=simple&searchCriteria[filter_groups][2][filters][0][condition_type]=eq&searchCriteria[filter_groups][2][filters][1][field]=type_id&searchCriteria[filter_groups][2][filters][1][value]=configurable&searchCriteria[filter_groups][2][filters][1][condition_type]=like")
            search_product_resource = Resource(search_product_path, oauth)
            search_product_dict = search_product_resource.get()
            search_product_json = search_product_dict.json()

            # Total searched products
            total_product_found = search_product_json.get("total_count")

            # Simple response text
            response = str(total_product_found) + " products found"
            if platform == 'facebook':
                fb_sr = fb.text_response([[response]])
            elif platform == 'google' or 'None':
                aog_sr = aog.simple_response([[response, response, False]])

            a = 0
            list_elements = []
            for p in search_product_json.get("items"):
                if start_point_search < 0:
                    start_point_search = 0
                    
                if a >= start_point_search and a < start_point_search + flow_3_page_size:
                    product_name = p.get("name")
                    product_sku = p.get("sku")
                    product_type = p.get("type_id")
                    if product_type == "configurable":
                        price = "As per options"
                    else:
                        price = p.get('price') # <--

                    product_description = " "
                    product_image = ""
                    special_price = " "
                    image_url = ""
                    for c in p['custom_attributes']:
                        try:
                            if c['attribute_code'] == "description":
                                product_description = df_lib.cleanhtml(c['value'])
                            elif c['attribute_code'] == 'image':
                                product_image = c['value']
                            elif c['attribute_code'] == "special_price": # <--
                                special_price = c['value'] # <--
                        except:
                            pass

                    image_url = base_url+ 'pub/media/catalog/product' + product_image

                    if product_type == "configurable":
                        price_text = "Price: "
                    else:
                        price_text = "Price: "+currency_symbol

                    if platform == 'facebook':
                        try:
                            fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text + "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(product_price), str(product_sku), image_url)
                        except:
                            try:
                                fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text + str(price), str(product_sku), image_url)
                            except:
                                fb_t_e = df_facebook.genric_list_fesponse(product_name, price_text + str(price), str(product_sku))
                        fb_t.add_element(fb_t_e)
                    elif platform == 'google' or 'None':
                        if total_product_found - start_point_search == 1:
                            one_product = 1
                            key = product_sku
                            text_response = "Reply 'Product detail' to get more details of "+ product_name +"."
                            suggestions = ["Product detail", "Back"]
                            try:
                                aog_sc = aog.basic_card(product_name, subtitle= price_text + "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(product_price), image=[image_url, "Sample_image"])                    
                            except:
                                try:
                                    aog_sc = aog.basic_card(product_name, subtitle= price_text + str(price), image=[image_url, "Sample_image"])
                                except:
                                    aog_sc = aog.basic_card(product_name, subtitle= price_text + str(price))
                        else:
                            try:
                                list_elements.append([product_name, price_text + "{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])
                            except:
                                try:
                                    list_elements.append([product_name, price_text + str(price), [product_sku, [product_name+str(1), product_name+str(2)]],[image_url, 'image_discription']])
                                except:
                                    list_elements.append([product_name, price_text + str(price), [product_sku, [product_name+str(1), product_name+str(2)]]])

                elif a >= start_point_search + flow_3_page_size:
                    break
                a += 1

            if platform == 'facebook':
                fb_sc = fb.custom_payload(fb_t.get_payload())
            elif platform == 'google' or 'None':
                # For 1 result card response, more than 1 result list response with pagination
                if total_product_found == 0:
                    text = "There is no product with name "+str(parameters)
                    aog_sc = aog.simple_response([[text, text, False]])
                else:
                    list_title = 'Searched Products'
                    if total_product_found - start_point_search != 1:
                        aog_sc = aog.list_select(list_title, list_elements)
        
    # Product details in card response format
    elif action == 'product_detail':
        suggestion_text_fb = "Use 'Back' to check previous response."
        product_list = []
        
        # Exctracting the product details using the Magento API
        parameters = req.get('queryResult').get('parameters').get("category_number") #get parameters from json
        if parameters == "":
            redirect = 1
            outputContexts = req.get('queryResult').get('outputContexts')
            for m in outputContexts:
                name = m.get("name")
                word = "one_item_list"
                if name[-len(word):] == word:
                    parameters = m.get('parameters').get('key_value')

        product_source_path = str(base_url+"rest/V1/products/?searchCriteria[filter_groups][0][filters][0][field]=sku&searchCriteria[filter_groups][0][filters][0][value]="+parameters+"&searchCriteria[filter_groups][0][filters][0][condition_type]=like")
        resource_product = Resource(product_source_path, oauth)
        product_dict = resource_product.get()
        product_list_json = product_dict.json()
        product_list.append(product_list_json)

        # Reading the features of the product (name, price, image url, url key, product description)
        # all try and excepts are either for solving SKU string format error or data insufficency of the product
        product_name = None
        product_type = None
        for b in product_list:
            try:
                product_name = b['items'][0]['name']
            except:
                try:
                    product_name = b['name']
                except:
                    pass
            try:
                product_id = b['items'][0]['id']
                button = base_url +"catalog/product/view/id/"+ str(product_id)
            except:
                try:
                    product_id = b['id']
                    button = base_url +"catalog/product/view/id/"+ str(product_id)
                except:
                    pass

            try:
                product_type = b['type_id']
            except:
                try:
                    product_type = b['items'][0]['type_id']
                except:
                    pass
            prices = []

            if product_type == "configurable":
                children_product_path = str(base_url+"rest/V1/configurable-products/"+str(parameters)+"/children")
                children_product_resource = Resource(children_product_path, oauth)
                children_product_dict = children_product_resource.get()
                children_product_json = children_product_dict.json()
                for child in children_product_json:
                    prices.append(child['price'])
                product_price = min(prices)
            else:
                try:
                    product_price = b['price']
                except:
                    try:
                        product_price = b['items'][0]['price']
                    except:
                        pass

            if product_type == "configurable":
                try:
                    configuration_options = b['extension_attributes']['configurable_product_options']
                except:
                    try:
                        configuration_options = b['items'][0]['extension_attributes']['configurable_product_options']
                    except:
                        pass
            product_description = " "
            product_image = ""
            image_url = ""
            meta_title = " "
            special_price = " "
            try:
                for c in b['items'][0]['custom_attributes']:
                    if c['attribute_code'] == "description":
                        product_description = df_lib.cleanhtml(c['value'])
                    elif c['attribute_code'] == 'image':
                        product_image = c['value']
                        image_url = base_url+ 'pub/media/catalog/product' + product_image
                    elif c['attribute_code'] == 'meta_title':
                        meta_title = c['value']
                    elif c['attribute_code'] == 'special_price':
                        special_price = c['value']
            except:
                try:
                    for c in b['items'][0]['custom_attributes']:
                        if c['attribute_code'] == "description":
                            product_description = df_lib.cleanhtml(c['value'])
                        elif c['attribute_code'] == 'image':
                            product_image = c['value']
                            image_url = base_url+ 'pub/media/catalog/product' + product_image
                        elif c['attribute_code'] == 'meta_title':
                            meta_title = c['value']
                        elif c['attribute_code'] == 'special_price':
                            special_price = c['value']
                except:
                    pass
        # if product type id is configurable than extract the conguration options of that product
        configuration_options_text = ""
        if product_type == "configurable":
            option_name = []
            options_text = []

            for option_attribute in configuration_options:
                attribute_code = option_attribute['attribute_id']
                option_name.append(option_attribute['label'])
                option_code = []
            
                for i in option_attribute['values']:
                    option_code.append(i['value_index']) 
            
                attribute_source_path = str(base_url+"rest/V1/products/attributes/"+str(attribute_code))
                product_resource = Resource(attribute_source_path, oauth)
                attribute_dict = product_resource.get()
                attribute_list_json = attribute_dict.json()
                attribute_options = attribute_list_json['options']
                option_text = ""
            
                for i in attribute_options:
                    try:
                        if (int(i['value']) in option_code):
                            option_text += str(i['label']) + ", "
                    except:
                        pass
                options_text.append(option_text)

            configuration_options_text = ""
            for i in range(len(option_name)):
                configuration_options_text += "  \n"+option_name[i]+": "+ options_text[i][:-2]

        if product_name == None:
            try:
                product_name = meta_title
            except:
                no_update = 1
    
        if product_type == "configurable":
            price_text = "Price starts from:"
        else:
            price_text = "Price:"

        if no_update != 1:
            text_response = "You have selected " + product_name
            
            if platform == 'facebook':
                try:
                    fb_t_e = df_facebook.genric_card_fesponse(product_name,price_text+" "+currency_symbol+"{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(product_price)+configuration_options_text+"\n"+product_description, button, "View Product", image_url)
                except:
                    try:
                        fb_t_e = df_facebook.genric_card_fesponse(product_name,price_text+" "+currency_symbol+str(product_price)+configuration_options_text+"\n"+product_description, button, "View Product", image_url)
                    except:
                        try:
                            fb_t_e = df_facebook.genric_card_fesponse(product_name,configuration_options_text+"\n"+product_description, button , "View Product", image_url)
                        except:
                            fb_t_e = df_facebook.genric_card_fesponse(product_name,configuration_options_text+"\n"+product_description, button , "View Product")
                fb_t.add_element(fb_t_e)
                fb_sc = fb.custom_payload(fb_t.get_payload())

            elif platform == 'google' or 'None':
                try:
                    aog_sc = aog.basic_card(product_name, subtitle= price_text+" "+currency_symbol+"{0:.2f}".format(float(special_price)) + "\nRegular Price: "+currency_symbol+ str(product_price)+configuration_options_text, formattedText=product_description, image=[image_url, "Sample_image"], buttons=[["View Product",button]])
                except:
                    try:
                        aog_sc = aog.basic_card(product_name, subtitle=price_text+" "+currency_symbol+str(product_price)+configuration_options_text, formattedText=product_description, image=[image_url, "Sample_image"], buttons=[["View Product",button]])
                    except:
                        aog_sc = aog.basic_card(product_name, subtitle=configuration_options_text, formattedText=product_description, image=[image_url, "Sample_image"], buttons=[["View Product",button]])

    # Suggestion chip for all the responses
    if action != "input.welcome" and one_product == 0:
        suggestions = ["Back"]

    # Suggestionchips for the back, previous, next indication to manage pagination and back functionality
    if one_product == 0 and (action == "previous" or action == "next" or action == "product_list" or action == "search_product" or action == "browse_product"): # <--
        if length_product_sku <= flow_1_page_size or length <= flow_2_page_size or total_product_found <= flow_3_page_size:
            no_suggestion = 1
        elif start_point_flow + flow_1_page_size >= length_product_sku or start_point_browse + flow_2_page_size >= length or start_point_search + flow_3_page_size >= total_product_found:
            suggestions = ["<Previous", "Back"]
            suggestion_text_fb = "Say PREVIOUS to see last browsed products."
        elif start_point_flow == 0 and start_point_browse == 0 and start_point_search == 0:
            suggestions = ["Back","Next>"]
            suggestion_text_fb = "Say NEXT to browse more products."
        else:
            suggestions = ["<Previous", "Back", "Next>"]
            suggestion_text_fb = "Say PREVIOUS or NEXT to browse more products."

    # Suggestion chips response
    if action != "category_names" or no_suggestion != 1:
        if platform == 'facebook':
            try:
                fb_suggestions = fb.quick_replies(suggestion_text_fb,suggestions)
            except:
                pass

        elif platform == 'google' or 'None':
            try:
                aog_suggestions = aog.suggestion_chips(suggestions)
            except:
                pass


    # Exctracting the saved previous responses from the output context for the Back functionality
    storage = []
    context = []

    mess = req.get('queryResult').get("outputContexts")
    if action != 'input.welcome':
        if platform != None:
            if platform == "google":
                storage_location = "./google_storage_data/"
            elif platform == "facebook":
                storage_location = "./facebook_storage_data/"
            with open(storage_location+userID+".json", 'r') as file:
                storage = json.load(file)
        for m in mess:
            name = m.get('name')
            if name[-4:] == "back":
                if platform == None:
                    # restore the previous all responses from the parameter to use either for back functionality or to append new data
                    stored = m.get("parameters").get("parameter")
                    for k in stored:
                        storage.append(k)
                else:
                    pass
            else:
                # Current output context
                context.append(m)

    # Fulfillment response object
    ff_response = fulfillment_response()

    # Simple text response
    if platform == 'facebook':
        fb_sr = fb.text_response([text_response])
    elif platform == 'google' or 'None':
        aog_sr = aog.simple_response([[text_response, text_response, False]])

    # Set default fulfillment text from the webhook
    fulfillment_text = 'List Response from webhook'
    ff_text = ff_response.fulfillment_text(fulfillment_text)

    # Fallback handling
    if action == "input.unknown" or no_update == 1:
        temp = storage[-1]
        ff_context = temp[1]
        ff_messages = temp[0]

    # Restore last response and output context
    elif action == "Back":
        temp = storage[-2]
        ff_context = temp[1]
        ff_messages = temp[0]
        storage.pop(len(storage)-1) # remove last response updated to manage the peoper flow
    
    # Set output message
    else:
        if platform == 'facebook':
            try:
                ff_messages = ff_response.fulfillment_messages([fb_sr, fb_sc, fb_suggestions])
            except:
                try:
                    ff_messages = ff_response.fulfillment_messages([fb_sr, fb_sc])
                except:
                    try:
                        ff_messages = ff_response.fulfillment_messages([fb_sr, fb_suggestions])
                    except:
                            ff_messages = ff_response.fulfillment_messages([fb_sr])
        elif platform == 'google' or 'None':
            try:
                ff_messages = ff_response.fulfillment_messages([aog_sr, aog_sc, aog_suggestions])
            except:
                try:
                    ff_messages = ff_response.fulfillment_messages([aog_sr, aog_sc])
                except:
                    try:
                        ff_messages = ff_response.fulfillment_messages([aog_sr, aog_suggestions])
                    except:
                        ff_messages = ff_response.fulfillment_messages([aog_sr])

        # Store current response for the future usage
        new_data = [ff_messages, context]
        if action == "input.welcome":
            storage = []
        if action == "search_product" and no_product_found:
            pass
        else:
            storage.append(new_data)
        

    # "Back" output context to store the all previous responses in the parameter
    if platform == None:
        contexts = [['Back', 100, {'parameter': storage}]]
    else:
        contexts = [['Back', 100, {'parameter': 0}]]

    # "Pagination" output context to store the flow indicator and current page number, current input query, text response for the pagination
    contexts.append(["pagination", 5, {'page_start': [flow_indicator, start_point_flow, start_point_browse, start_point_search, search_product_name, text_response, last_num_of_product]}])
    if redirect == 1:
        contexts.append(['Product-followup', 1, {"category_number": [parameters]}])
    if action == "search_product" and no_product_found:
        contexts.append(['SearchProduct-followup', 1, {}])

    if one_product and (platform == 'None' or "google"):
    # Set context when there is only one ietm in the list to pass the key value
        contexts.append(["one_item_list", 1, {'key_value': key}])

    # Set output context
    session = req.get("session") # Get session name from fulfilment reqest
    ff_out_context  = ff_response.output_contexts(session, contexts)

    # Save output context (with their paramenters) of the last response in the output contexts
    if action == "Back" or action == "input.unknown" or no_update == 1:
        for i in range(len(ff_context)):
            if ff_context[i]["name"][-len("pagination"):] != "pagination":
                ff_out_context.get('output_contexts').append(ff_context[i])
    
    # Change of the simple response text in case of fallback handling
    if no_update == 1 or action == "input.unknown":
        text_response = "Sorry. I did not get you.\nPlease select from the given options."
        if platform == 'facebook':
            ff_messages['fulfillment_messages'][0]['text']['text'][0] = text_response
        elif platform == "google" or platform == None:
            ff_messages['fulfillment_messages'][0]['simpleResponses']['simpleResponses'][0]['displayText'] = text_response

    reply = ff_response.main_response(ff_text, ff_messages, ff_out_context)

    # Give all user a unique User ID and store into userStorage of the assistant
    if platform == "google":
        if userID == None:
            userID = uuid.uuid1()
            reply['payload'] = {
                'google': {
                    'userStorage': userID
                }
            }
        storage_location = "./google_storage_data/"
    elif platform == "facebook":
        storage_location = "./facebook_storage_data/"

    # Store the responses in the file for Back functionality
    if platform != None:
        if os.path.isdir(storage_location) == False:
            os.mkdir(storage_location)
        with open(storage_location+userID+".json", 'w') as file:
            json.dump(storage, file)

    # Webhook response in the json format to the dialogFlow
    return JsonResponse(reply, safe = False)