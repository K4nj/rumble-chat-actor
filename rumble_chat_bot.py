#!/usr/bin/env python3
"""Rumble Chat Bot

S.D.G."""

import time
from cocorum import RumbleAPI, utils
from cocorum.ssechat import SSEChatAPI
import selenium
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

#How long to wait after performing any browser action, for the webpage to load its response
BROWSER_ACTION_DELAY = 2

#Popout chat url. Format with chat_id
CHAT_URL = "https://rumble.com/chat/popup/{chat_id}"

BOT_MESSAGE_PREFIX = "🤖: "

#Load credentials and API URL
CREDENTIALS_FILE = "rumble_credentials.txt"
API_URL_FILE = "api_url.txt"

with open(CREDENTIALS_FILE) as f:
    USERNAME, PASSWORD = f.read().strip().splitlines()

with open(API_URL_FILE) as f:
    API_URL = f.read().strip()

#Profile directory to use
PROFILE_DIR = "/home/wilbur/.mozilla/firefox/z4gntk86.Selenium"

#Levels of mute to discipline a user with
MUTE_LEVELS = {
    "5" : "cmi js-btn-mute-current-5",
    "stream" : "cmi js-btn-mute-current",
    "forever" : "cmi js-btn-mute-for-account",
    }

class RumbleChatBot():
    """Bot that interacts with Rumble chat"""
    def __init__(self, stream_id = None, init_message = "Hello, Rumble world!", profile_dir = None):
        """Pass the stream ID you want to connect to. Defaults to latest livestream"""

        #Get Live Stream API
        self.rum_api = RumbleAPI(API_URL)

        #A stream ID was passed
        if stream_id:
            #It is not our livestream, Live Stream API functions are not available
            if stream_id not in self.rum_api.livestreams.keys():
                self.api_stream = None

            #It is our livestream, we can use the Live Stream API
            else:
                self.api_stream = self.rum_api.livestreams[stream_id]
            self.stream_id = stream_id

        #A stream ID was not passed
        else:
            self.api_stream = self.rum_api.latest_livestream

            #No streams are live shown on the API
            if not self.api_stream:
                raise ValueError("No stream ID was passed and you are not live")

            self.stream_id = self.api_stream.stream_id

        #Get SSE chat and empty the mailbox
        self.ssechat = SSEChatAPI(stream_id = self.stream_id)
        self.ssechat.mailbox = []

        #Set browser profile directory of we have one
        options = webdriver.FirefoxOptions()
        if profile_dir:
            options.add_argument("-profile")
            options.add_argument(profile_dir)

        #Get browser
        self.browser = webdriver.Firefox(options = options)
        self.browser.minimize_window()
        self.browser.get(CHAT_URL.format(chat_id = self.ssechat.chat_id))
        assert "Chat" in self.browser.title

        #Sign in to chat, unless we are already
        try:
            self.browser.find_element(By.CLASS_NAME, "chat--sign-in").click()
        except selenium.common.exceptions.NoSuchElementException:
            print("Could not find sign-in button, already signed in.")
        else:
            time.sleep(BROWSER_ACTION_DELAY)
            self.browser.find_element(By.ID, "login-username").send_keys(USERNAME + Keys.RETURN)
            self.browser.find_element(By.ID, "login-password").send_keys(PASSWORD + Keys.RETURN)
        time.sleep(BROWSER_ACTION_DELAY)

        #Send an initialization message to get wether we are moderator or not
        self.send_message(init_message)

        #Wait until we get that message
        while (m := self.ssechat.next_chat_message()).user.username != USERNAME:
            pass

        assert "moderator" in m.user.badges or "admin" in m.user.badges

    def send_message(self, text):
        """Send a message in chat"""
        if "\n" in text:
            raise ValueError("Message cannot contain newlines")
        self.browser.find_element(By.ID, "chat-message-text-input").send_keys(BOT_MESSAGE_PREFIX + text + Keys.RETURN)

    def hover_element(self, element):
        """Hover over a selenium element"""
        ActionChains(self.browser).move_to_element(element).perform()

    def open_moderation_menu(self, message):
        """Open the moderation menu of a message"""

        #The passed message was a li element
        if isinstance(message, webdriver.remote.webelement.WebElement) and message.tag_name == "li":
            message_li = message
            message_id = message_li.get_attribute("data-message-id")

        #Find the message by ID
        elif isinstance(message, int):
            message_id = message
            message_li = self.browser.find_element(By.XPATH, f"//li[@class='chat-history--row js-chat-history-item'][@data-message-id='{message_id}']")

        #The message has a message ID attribute
        elif hasattr(message, "message_id"):
            message_id = message.message_id
            message_li = self.browser.find_element(By.XPATH, f"//li[@class='chat-history--row js-chat-history-item'][@data-message-id='{message_id}']")

        #Not a valid message type
        else:
            raise TypeError("Message must be ID, li element, or have message_id attribute")
            
        #Hover over the message
        self.hover_element(message_li)
        #Find the moderation menu
        menu_bttn = self.browser.find_element(By.XPATH, f"//li[@class='chat-history--row js-chat-history-item'][@data-message-id='{message_id}']/button[@class='js-moderate-btn chat-history--kebab-button']")
        #Click the moderation menu button
        menu_bttn.click()

        return message_id

    def delete_message(self, message):
        """Delete a message in the chat"""
        m_id = self.open_moderation_menu(message)
        del_bttn = self.browser.find_element(By.XPATH, f"//button[@class='cmi js-btn-delete-current'][@data-message-id='{m_id}']")
        del_bttn.click()
        
    def mute_by_message(self, message, mute_level = "5"):
        """Mute a user by message"""
        self.open_moderation_menu(message)
        timeout_bttn = self.browser.find_element(By.XPATH, f"//button[@class='{MUTE_LEVELS[mute_level]}']")
        timeout_bttn.click()

    def mute_by_appearname(self, name, mute_level = "5"):
        """Mute a user by the name they are appearing with"""
        #Find any chat message by this user
        message_li = self.browser.find_element(By.XPATH, f"//li[@class='chat-history--row js-chat-history-item'][@data-username='{name}']")
        self.mute_by_message(message_li = message_li, mute_level = mute_level)

    def pin_message(self, message):
        """Pin a message by ID or li element"""
        self.open_moderation_menu(message)
        pin_bttn = self.browser.find_element(By.XPATH, f"//button[@class='cmi js-btn-pin-current']")
        pin_bttn.click()

    def unpin_message(self, message):
        """Unpin the currently pinned message"""
        try:
            unpin_bttn = self.browser.find_element(By.XPATH, f"//button[@data-js='remove_pinned_message_button']")
        except selenium.common.exceptions.NoSuchElementException:
            return False #No message was pinned
        else:
            unpin_bttn.click()

    def quit(self):
        """Shut down everything"""
        self.browser.quit()
        # TODO how to close an SSEClient?
        # self.ssechat.client.close()
