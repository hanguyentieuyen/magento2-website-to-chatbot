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
from library.facebook_template_lib import TemplateElement, TemplateElementButton, FacebookTemplate # <--

# Class object to generate facebook templates
fb_t = FacebookTemplate()

def genric_list_response(name, subtitle, id, image_url  = None, index=None):
    """ Return element for the list response for the Facebook Messenger """

    if index != None:
        fb_t_e = TemplateElement(name[index], subtitle)
        if image_url != None:
            fb_t_e.add_image_url(image_url)
        fb_t_e2_b = TemplateElementButton('postback', name[index])
        fb_t_e2_b.add_payload(str(id[index]))
    else:
        fb_t_e = TemplateElement(name, subtitle)
        if image_url != None:
            fb_t_e.add_image_url(image_url)
        fb_t_e2_b = TemplateElementButton('postback', name)
        fb_t_e2_b.add_payload(id)

    fb_t_e2_b = fb_t_e2_b.get_button()
    fb_t_e.add_button(fb_t_e2_b)

    return fb_t_e.get_element()

def genric_card_response(name, subtitle, click_url,button_name, image_url = None, index=None):
    """ Return element for the card response for the Facebook Messenger """

    fb_t_e = TemplateElement(name, subtitle)
    if image_url != None:
        fb_t_e.add_image_url(image_url)
    fb_t_e2_b = TemplateElementButton('web_url', button_name)
    fb_t_e2_b.add_web_url(click_url)
    fb_t_e2_b = fb_t_e2_b.get_button()
    fb_t_e.add_button(fb_t_e2_b)

    return fb_t_e.get_element()

