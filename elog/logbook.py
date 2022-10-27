import requests
import urllib.parse
import os
import builtins
import re
import sys
from elog.logbook_exceptions import *
from datetime import datetime


class Logbook(object):
    """
    Logbook provides methods to interface with logbook on location: "server:port/subdir/logbook". User can create,
    edit, delete logbook messages.
    """

    def __init__(self, hostname, logbook='', port=None, user=None, password=None, subdir='', use_ssl=True,
                 encrypt_pwd=True):
        """
        :param hostname: elog server hostname. If whole url is specified here, it will be parsed and arguments:
                         "logbook, port, subdir, use_ssl" will be overwritten by parsed values.
        :param logbook: name of the logbook on the elog server
        :param port: elog server port (if not specified will default to '80' if use_ssl=False or '443' if use_ssl=True
        :param user: username (if authentication needed)
        :param password: password (if authentication needed) Password will be encrypted with sha256 unless
                         encrypt_pwd=False (default: True)
        :param subdir: subdirectory of logbooks locations
        :param use_ssl: connect using ssl (ignored if url starts with 'http://'' or 'https://'?
        :param encrypt_pwd: To avoid exposing password in the code, this flag can be set to False and password
                            will then be handled as it is (user needs to provide sha256 encrypted password with
                            salt= '' and rounds=5000)
        :return:
        """
        hostname = hostname.strip()

        # parse url to see if some parameters are defined with url
        parsed_url = urllib.parse.urlsplit(hostname)

        # ---- handle SSL -----
        # hostname must be modified according to use_ssl flag. If hostname starts with https:// or http://
        # the use_ssl flag is ignored
        url_scheme = parsed_url.scheme
        if url_scheme == 'http':
            use_ssl = False

        elif url_scheme == 'https':
            use_ssl = True

        elif not url_scheme:
            # add http or https
            if use_ssl:
                url_scheme = 'https'
            else:
                url_scheme = 'http'

        # ---- handle port -----
        # 1) by default use port defined in the url
        # 2) remove any 'default' ports such as 80 for http and 443 for https
        # 3) if port not defined in url and not 'default' add it to netloc

        netloc = parsed_url.netloc
        if netloc == "" and "localhost" in hostname:
            netloc = 'localhost'
        netloc_split = netloc.split(':')
        if len(netloc_split) > 1:
            # port defined in url --> remove if needed
            port = netloc_split[1]
            if (port == 80 and not use_ssl) or (port == 443 and use_ssl):
                netloc = netloc_split[0]

        else:
            # add port info if needed
            if port is not None and not (port == 80 and not use_ssl) and not (port == 443 and use_ssl):
                netloc += ':{}'.format(port)

        # ---- handle subdir and logbook -----
        # parsed_url.path = /<subdir>/<logbook>/

        # Remove last '/' for easier parsing
        url_path = parsed_url.path
        if url_path.endswith('/'):
            url_path = url_path[:-1]

        splitted_path = url_path.split('/')
        if url_path and len(splitted_path) > 1:
            # If here ... then at least some part of path is defined.

            # If logbook defined --> treat path current path as subdir and add logbook at the end
            # to define the full path. Else treat existing path as <subdir>/<logbook>.
            # Put first and last '/' back on its place
            if logbook:
                url_path += '/{}'.format(logbook)
            else:
                logbook = splitted_path[-1]

        else:
            # There is nothing. Use arguments.
            url_path = subdir + '/' + logbook

        # urllib.parse.quote replaces special characters with %xx escapes
        # self._logbook_path = urllib.parse.quote('/' + url_path + '/').replace('//', '/')
        self._logbook_path = ('/' + url_path + '/').replace('//', '/')

        self._url = url_scheme + '://' + netloc + self._logbook_path
        self.logbook = logbook
        self._user = user
        self._password = _handle_pswd(password, encrypt_pwd)

    def post(self, message, msg_id=None, reply=False, attributes=None, attachments=None,
             suppress_email_notification=False, encoding=None, timeout=None, **kwargs):
        """
        Posts message to the logbook. If msg_id is not specified new message will be created, otherwise existing
        message will be edited, or a reply (if reply=True) to it will be created. This method returns the msg_id
        of the newly created message.

        :param message: string with message text
        :param msg_id: ID number of message to edit or reply. If not specified new message is created.
        :param reply: If 'True' reply to existing message is created instead of editing it
        :param attributes: Dictionary of attributes. Following attributes are used internally by the elog and will be
                           ignored: Text, Date, Encoding, Reply to, In reply to, Locked by, Attachment
        :param attachments: list of:
                                  - file like objects which read() will return bytes (if file_like_object.name is not
                                    defined, default name "attachment<i>" will be used.
                                  - paths to the files
                            All items will be appended as attachment to the elog entry. In case of unknown
                            attachment an exception LogbookInvalidAttachment will be raised.
        :param suppress_email_notification: If set to True or 1, E-Mail notification will be suppressed, defaults to False.
        :param encoding: Defines encoding of the message. Can be: 'plain' -> plain text, 'html'->html-text,
                         'ELCode' --> elog formatting syntax
        :param timeout: Define the timeout to be used by the post request. Its value is directly passed to the requests
                        post. Use None to disable the request timeout.
        :param kwargs: Anything in the kwargs will be interpreted as attribute. e.g.: logbook.post('Test text',
                       Author='Rok Vintar), "Author" will be sent as an attribute. If named same as one of the
                       attributes defined in "attributes", kwargs will have priority.

        :return: msg_id
        """

        attributes = attributes or {}
        attributes = {**attributes, **kwargs}  # kwargs as attributes with higher priority

        attachments = attachments or []

        if encoding is not None:
            if encoding not in ['plain', 'HTML', 'ELCode']:
                raise LogbookMessageRejected('Invalid message encoding. Valid options: plain, HTML, ELCode.')
            attributes['Encoding'] = encoding

        if suppress_email_notification:
            attributes["suppress"] = 1

        # THE ATTACHMENT STRATEGY WHEN DEALING WITH POST MODIFICATION
        #
        # 1. Does the message on the server have already attachments?
        #    1.1 - We read the message getting the existing attachment list.
        #    1.2 - Add to the attributes dictionary one line for each attachment like this:
        #       attributes['attachmentN'] = timestamped_filename_name
        #
        # 2. Do we have new attachments?
        #    2.1 - Those are in the new_attachment_list. This is a list of this type:
        #       [ ('attfileN', ('filename', fileobject)) ]
        #    2.2 - We need to loop over all the new attachments:
        #       2.2.1 - Does a file already on the server with the same name exist?
        #         2.2.1.1 - No: OK. Then we go ahead with the next attachment.
        #         2.2.1.2 - Yes:
        #           2.2.1.2.1 - Are the two files identical?
        #               2.2.1.2.1.1 - Yes: then we remove this current entry from the new_attachment_list and we leave the one
        #                      already on server.
        #               2.2.1.2.1.2 - No:
        #                  2.2.1.2.1.2.1 - Then the file has been update.
        #                  2.2.1.2.1.2.2 - We need to remove the file on server first (using special post)
        #                  2.2.1.2.1.2.3 - We have to remove the old attachment from the attributes dictionary.
        #

        if attachments:
            # here we accomplish point 2.1.
            # new_attachment_list is something like [ ('attfileN', ('filename', fileobject)) ]
            new_attachment_list, objects_to_close = self._prepare_attachments(attachments)
        else:
            objects_to_close = list()
            new_attachment_list = list()

        attributes_to_edit = dict()
        if msg_id:
            # Message exists, we can continue
            if reply:
                # Verify that there is a message on the server, otherwise do not reply to it!
                self._check_if_message_on_server(msg_id)  # raises exception in case of none existing message
                attributes['reply_to'] = str(msg_id)
            else:  # Edit existing
                attributes['edit_id'] = str(msg_id)
                attributes['skiplock'] = '1'

                # here we accomplish point 1.1.
                # existing_attachments_list is something like:
                # [ 'https://elog.url.com/logbook/timestamped_filename' ]
                msg_to_edit, attributes_to_edit, existing_attachments_list = self.read(msg_id)

                for attribute, data in attributes.items():
                    new_data = attributes.get(attribute)
                    if new_data is not None:
                        attributes_to_edit[attribute] = new_data

                i = 0
                existing_attachments_filename_list = list()
                for attachment in existing_attachments_list:
                    # here we accomplish point 1.2. We strip the timestamped_filename from the whole URL.
                    attributes_to_edit[f'attachment{i}'] = os.path.basename(attachment)
                    existing_attachments_filename_list.append(os.path.basename(attachment)[14:])
                    i += 1

                # let's accomplish 2.2. Loop over all new attachment
                duplicate_attachment_list = list()
                for new_attachment in new_attachment_list:
                    # the new_attachment_list is something like:
                    # [ ('attfileN', ('filename', fileobject)) ]
                    new_attachment_filename = new_attachment[1][0]
                    if new_attachment_filename in existing_attachments_filename_list:
                        # a file with the same name existing already on the server.
                        # we need to check if the two files are the same.
                        # read the content of the new file
                        new_attachment_content = new_attachment[1][1].read()
                        # don't forget to reset the fileobj to the beginning of the file
                        new_attachment[1][1].seek(0)
                        # get the existing attachment content
                        attachment_index = existing_attachments_filename_list.index(new_attachment_filename)
                        existing_attachment_content = self.download_attachment(
                            url=existing_attachments_list[attachment_index],
                            timeout=timeout
                        )
                        # check if the two contents are the same
                        if new_attachment_content == existing_attachment_content:
                            # yes. then we don't upload a second copy. we remove the current entry from the list
                            duplicate_attachment_list.append(new_attachment)
                        else:
                            # no. they are not the same file. we will replace the existing file with the new one
                            # first: we need to remove the attachment from the server using the dedicated method
                            self.delete_attachment(msg_id, attributes=attributes_to_edit,
                                                   attachment_id=attachment_index,
                                                   timeout=timeout, text=msg_to_edit)
                            # now we can remove this attachment from the auxiliary lists.
                            existing_attachments_filename_list.pop(attachment_index)
                            existing_attachments_list.pop(attachment_index)
                            # now we need to rebuild the attributes dictionary for the part concerning the attachments.
                            # we remove all of them first
                            keys_to_be_removed = list()
                            for key in attributes_to_edit.keys():
                                if key.startswith('attachment'):
                                    keys_to_be_removed.append(key)
                                if key.startswith('delatt'):
                                    keys_to_be_removed.append(key)
                            for key in keys_to_be_removed:
                                del attributes_to_edit[key]

                            # now we rebuild it
                            for i, attachment in enumerate(existing_attachments_list):
                                attributes_to_edit[f'attachment{i}'] = os.path.basename(attachment)

                # remove all duplicate attachments from the new_attachment_list
                for attach in duplicate_attachment_list:
                    new_attachment_list.remove(attach)

        else:
            # As we create a new message, specify creation time if not already specified in attributes
            if 'When' not in attributes:
                attributes['When'] = int(datetime.now().timestamp())

        if not attributes_to_edit:
            attributes_to_edit = attributes

        # Remove any attributes that should not be sent
        _remove_reserved_attributes(attributes_to_edit)

        # Make requests module think that Text is a "file". This is the only way to force requests to send data as
        # multipart/form-data even if there are no attachments. Elog understands only multipart/form-data
        new_attachment_list.append(('Text', ('', message.encode('iso-8859-1'))))

        # Base attributes are common to all messages
        self._add_base_msg_attributes(attributes_to_edit)

        # Keys in attributes cannot have certain characters like whitespaces or dashes for the http request
        attributes_to_edit = _replace_special_characters_in_attribute_keys(attributes_to_edit)

        # All string values in the attributes must be encoded in latin1
        attributes_to_edit = _encode_values(attributes_to_edit)

        try:
            response = requests.post(self._url, data=attributes_to_edit, files=new_attachment_list,
                                     allow_redirects=False, verify=False, timeout=timeout)

            # Validate response. Any problems will raise an Exception.
            resp_message, resp_headers, resp_msg_id = _validate_response(response)

            # Close file like objects that were opened by the elog (if  path
            for file_like_object in objects_to_close:
                if hasattr(file_like_object, 'close'):
                    file_like_object.close()

        except requests.Timeout as e:
            # Catch here a timeout o the post request.
            # Raise the logbook excetion and let the user handle it
            raise LogbookServerTimeout('{0} method cannot be completed because of a network timeout:\n' +
                                       '{1}'.format(sys._getframe().f_code.co_name, e))

        except requests.RequestException as e:
            # Check if message on server.
            self._check_if_message_on_server(msg_id)  # raises exceptions if no message or no response from server

            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to post a message, ' + 'because of:\n' +
                                       '{0}'.format(e))

        # Any error before here should raise an exception, but check again for nay case.
        if not resp_msg_id or resp_msg_id < 1:
            raise LogbookInvalidMessageID('Invalid message ID: ' + str(resp_msg_id) + ' returned')
        return resp_msg_id

    def read(self, msg_id, timeout=None):
        """
        Reads message from the logbook server and returns tuple of (message, attributes, attachments) where:
        message: string with message body
        attributes: dictionary of all attributes returned by the logbook
        attachments: list of urls to attachments on the logbook server

        :param msg_id: ID of the message to be read
        :param timeout: The timeout value to be passed to the get request.
        :return: message, attributes, attachments
        """

        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()

        try:
            self._check_if_message_on_server(msg_id)  # raises exceptions if no message or no response from server
            response = requests.get(self._url + str(msg_id) + '?cmd=download', headers=request_headers,
                                    allow_redirects=False, verify=False, timeout=timeout)

            # Validate response. If problems Exception will be thrown.
            resp_message, resp_headers, resp_msg_id = _validate_response(response)


        except requests.Timeout as e:

            # Catch here a timeout o the post request.

            # Raise the logbook excetion and let the user handle it

            raise LogbookServerTimeout('{0} method cannot be completed because of a network timeout:\n' +
                                       '{1}'.format(sys._getframe().f_code.co_name, e))

        except requests.RequestException as e:
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to read the message with ID: ' + str(msg_id) +
                                       'because of:\n' + '{0}'.format(e))

        # Parse message to separate message body, attributes and attachments
        attributes = dict()
        attachments = list()

        returned_msg = resp_message.decode('iso-8859-1', 'ignore').splitlines()
        delimiter_idx = returned_msg.index('========================================')

        message = '\n'.join(returned_msg[delimiter_idx + 1:])
        for line in returned_msg[0:delimiter_idx]:
            line = line.split(': ')
            data = ''.join(line[1:])
            if line[0] == 'Attachment':
                if not data:
                    # Treat the empty string as special case,
                    # otherwise the split below returns [""] and attachments is [self._url]
                    attachments = []
                else:
                    attachments = data.split(',')
                    # Here are only attachment names, make a full url out of it, so they could be
                    # recognisable by others, and downloaded if needed
                    attachments = [self._url + '{0}'.format(i) for i in attachments]
            else:
                attributes[line[0]] = data

        return message, attributes, attachments

    def delete_attachment(self, msg_id, text, attributes, attachment_id, timeout=None):

        attributes[f'delatt{attachment_id}'] = 'Delete'
        attributes['cmd'] = 'Update'
        attributes['exp'] = self.logbook
        if self._user:
            attributes['unm'] = self._user
        if self._password:
            attributes['upwd'] = self._password

        just_text = list()
        just_text.append(('Text', ('', text.encode('iso-8859-1'))))
        try:
            response = requests.post(self._url, data=attributes, verify=False, allow_redirects=False,
                                     files=just_text)
        except requests.Timeout as e:
            # Catch here a timeout o the post request.
            # Raise the logbook excetion and let the user handle it
            raise LogbookServerTimeout('{0} method cannot be completed because of a network timeout:\n' +
                                       '{1}'.format(sys._getframe().f_code.co_name, e))
        except requests.RequestException as e:
            # Check if message on server.
            self._check_if_message_on_server(msg_id)  # raises exceptions if no message or no response from server

            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to post a message, ' + 'because of:\n' +
                                       '{0}'.format(e))
        finally:
            del attributes[f'delatt{attachment_id}']

    def delete(self, msg_id, timeout=None):
        """
        Deletes message thread (!!!message + all replies!!!) from logbook.
        It also deletes all of attachments of corresponding messages from the server.

        :param msg_id: message to be deleted
        :param timeout: timeout value to be passed to the get request
        :return:
        """

        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()

        try:
            self._check_if_message_on_server(msg_id)  # check if something to delete

            response = requests.get(self._url + str(msg_id) + '?cmd=Delete&confirm=Yes', headers=request_headers,
                                    allow_redirects=False, verify=False, timeout=timeout)

            _validate_response(response)  # raises exception if any other error identified

        except requests.Timeout as e:
            # Catch here a timeout o the post request.
            # Raise the logbook excetion and let the user handle it
            raise LogbookServerTimeout('{0} method cannot be completed because of a network timeout:\n' +
                                       '{1}'.format(sys._getframe().f_code.co_name, e))

        except requests.RequestException as e:
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to delete the message with ID: ' + str(msg_id) +
                                       'because of:\n' + '{0}'.format(e))

        # Additional validation: If successfully deleted then status_code = 302. In case command was not executed at
        # all (not English language --> no download command supported) status_code = 200 and the content is just a
        # html page of this whole message.
        if response.status_code == 200:
            raise LogbookServerProblem('Cannot process delete command (only logbooks in English supported).')

    def search(self, search_term, n_results=20, scope="subtext", timeout=None):
        """
        Searches the logbook and returns the message ids.

        :param timeout: timeout value to be passed to the get request

        """
        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()

        # Putting n_results = 0 crashes the elog. also in the web-gui.
        n_results = 1 if n_results < 1 else n_results

        params = {
            "mode": "full",
            "reverse": "1",
            "npp": n_results
        }
        if type(search_term) is dict:
            params.update(search_term)
        else:
            params.update({scope: search_term})

        # Remove empty entries from params, since ELog will redirect such requests
        # and remove them anyway, but the redirect leads to unexpected results
        keys = list(params.keys())
        for key in keys:
            if params[key] == "":
                params.pop(key)

        try:
            response = requests.get(self._url, params=params, headers=request_headers,
                                    allow_redirects=False, verify=False, timeout=timeout)

            # Validate response. If problems Exception will be thrown.
            _validate_response(response)
            resp_message = response

        except requests.Timeout as e:
            # Catch here a timeout o the post request.
            # Raise the logbook excetion and let the user handle it
            raise LogbookServerTimeout('{0} method cannot be completed because of a network timeout:\n' +
                                       '{1}'.format(sys._getframe().f_code.co_name, e))

        except requests.RequestException as e:
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to read message ids '
                                       'because of:\n' + '{0}'.format(e))

        from lxml import html
        tree = html.fromstring(resp_message.content)
        message_ids = tree.xpath('(//tr/td[@class="list1" or @class="list2"][1])/a/@href')
        message_ids = [int(m.split("/")[-1]) for m in message_ids]
        return message_ids

    def get_last_message_id(self, timeout=None):
        ids = self.get_message_ids(timeout)
        if len(ids) > 0:
            return ids[0]
        else:
            return None

    def get_message_ids(self, timeout=None):
        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()

        try:
            response = requests.get(self._url + 'page', headers=request_headers,
                                    allow_redirects=False, verify=False, timeout=timeout)

            # Validate response. If problems Exception will be thrown.
            _validate_response(response)
            resp_message = response

        except requests.Timeout as e:
            # Catch here a timeout o the post request.
            # Raise the logbook exception and let the user handle it
            raise LogbookServerTimeout('{0} method cannot be completed because of a network timeout:\n' +
                                       '{1}'.format(sys._getframe().f_code.co_name, e))

        except requests.RequestException as e:
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to read message ids '
                                       'because of:\n' + '{0}'.format(e))

        from lxml import html
        tree = html.fromstring(resp_message.content)
        message_ids = tree.xpath('(//tr/td[@class="list1" or @class="list2"][1])/a/@href')
        message_ids = [int(m.split("/")[-1]) for m in message_ids]
        return message_ids

    def download_attachment(self, url, timeout=None):
        """
        Download an attachment from the specified url.
        """
        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()

        try:
            response = requests.get(url, headers=request_headers, allow_redirects=False,
                                    verify=False, timeout=timeout)
            # If there is no message code 200 will be returned (OK) and _validate_response will not recognise it
            # but there will be some error in the html code.
            resp_message, resp_headers, resp_msg_id = _validate_response(response)

        except requests.Timeout as e:
            # Catch here a timeout of the get request.
            # Raise the logbook exception and let the user handle it
            raise LogbookServerTimeout('{0} method cannot be completed because of a network timeout:\n' +
                                       '{1}'.format(sys._getframe().f_code.co_name, e))

        return resp_message

    def _check_if_message_on_server(self, msg_id, timeout=None):
        """Try to load page for specific message. If there is a html tag like <td class="errormsg"> then there is no
        such message.

        :param msg_id: ID of message to be checked
        :params timeout: The value of timeout to be passed to the get request
        :return:
        """

        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()
        try:
            response = requests.get(self._url + str(msg_id), headers=request_headers, allow_redirects=False,
                                    verify=False, timeout=timeout)

            # If there is no message code 200 will be returned (OK) and _validate_response will not recognise it
            # but there will be some error in the html code.
            resp_message, resp_headers, resp_msg_id = _validate_response(response)
            # If there is no message, code 200 will be returned (OK) but there will be some error indication in
            # the html code.
            if re.findall('<td.*?class="errormsg".*?>.*?</td>',
                          resp_message.decode('utf-8', 'ignore'),
                          flags=re.DOTALL):
                raise LogbookInvalidMessageID('Message with ID: ' + str(msg_id) + ' does not exist on logbook.')

        except requests.Timeout as e:
            # Catch here a timeout o the post request.
            # Raise the logbook exception and let the user handle it
            raise LogbookServerTimeout('{0} method cannot be completed because of a network timeout:\n' +
                                       '{1}'.format(sys._getframe().f_code.co_name, e))

        except requests.RequestException as e:
            raise LogbookServerProblem('No response from the logbook server.\nDetails: ' + '{0}'.format(e))

    def _add_base_msg_attributes(self, data):
        """
        Adds base message attributes which are used by all messages.
        :param data: dict of current attributes
        :return: content string
        """
        data['cmd'] = 'Submit'
        data['exp'] = self.logbook
        if self._user:
            data['unm'] = self._user
        if self._password:
            data['upwd'] = self._password

    def _prepare_attachments(self, files):
        """
        Parses attachments to content objects. Attachments can be:
            - file like objects: must have method read() which returns bytes. If it has attribute .name it will be used
              for attachment name, otherwise generic attribute<i> name will be used.
            - path to the file on disk

        Note that if attachment is an url pointing to the existing Logbook server it will be ignored and no
        exceptions will be raised. This can happen if attachments returned with read_method are resend.

        :param files: list of file like objects or paths
        :return: two lists:
            - one list of prepared attachment in the form of
                [ ('attfileN', ('filename', file_object)) ]

            - one list of object to be closed. all files that are passed as string or path are opened by the library
                and need to be closed by the library.
        """
        prepared = list()
        i = 0
        objects_to_close = list()  # objects that are created (opened) by elog must be later closed
        for file_obj in files:
            if hasattr(file_obj, 'read'):
                attribute_name = f'attfile{i}'
                filename = attribute_name  # If file like object has no name specified use this one
                candidate_filename = os.path.basename(file_obj.name)

                if candidate_filename:  # use only if not empty string
                    filename = candidate_filename
                i += 1

            elif isinstance(file_obj, str):
                # Check if it is:
                #           - a path to the file --> open file and append
                #           - an url pointing to the existing Logbook server --> ignore

                filename = ""
                attribute_name = ""

                if os.path.isfile(file_obj):

                    attribute_name = f'attfile{i}'
                    file_obj = builtins.open(file_obj, 'rb')
                    filename = os.path.basename(file_obj.name)

                    objects_to_close.append(file_obj)
                    i += 1

                elif not file_obj.startswith(self._url):
                    raise LogbookInvalidAttachmentType('Invalid type of attachment: \"' + file_obj + '\".')
            else:
                raise LogbookInvalidAttachmentType('Invalid type of attachment[' + str(i) + '].')

            # prepared.append((attribute_name, (filename, file_obj)))
            prepared.append((attribute_name, (filename, file_obj)))

        return prepared, objects_to_close

    def _make_user_and_pswd_cookie(self):
        """
        prepares user name and password cookie. It is sent in header when posting a message.
        :return: user name and password value for the Cookie header
        """
        cookie = ''
        if self._user:
            cookie += 'unm=' + self._user + ';'
        if self._password:
            cookie += 'upwd=' + self._password + ';'

        return cookie


def _remove_reserved_attributes(attributes):
    """
    Removes elog reserved attributes (from the attributes dict) that can not be sent.

    :param attributes: dictionary of attributes to be cleaned.
    :return:
    """

    if attributes:
        attributes.get('$@MID@$', None)
        attributes.pop('Date', None)
        attributes.pop('Attachment', None)
        attributes.pop('Text', None)  # Remove this one because it will be send attachment like


def _encode_values(attributes):
    """
    prepares a dictionary of the attributes with latin1 encoded string values.

    :param attributes: dictionary of attributes to ve encoded
    :return: dictionary with encoded string attributes
    """

    encoded_attributes = {}
    for key, value in attributes.items():
        if isinstance(value, str):
            encoded_attributes[key] = value.encode('iso-8859-1')
        else:
            encoded_attributes[key] = value
    return encoded_attributes


def _replace_special_characters_in_attribute_keys(attributes):
    """
    Replaces special characters in elog attribute keys by underscore, otherwise attribute values will be erased in
    the http request. This is using the same replacement elog itself is using to handle these cases

    :param attributes: dictionary of attributes to be cleaned.
    :return: attributes with replaced keys
    """
    return {re.sub('[^0-9a-zA-Z]', '_', key): value for key, value in attributes.items()}


def _validate_response(response):
    """ Validate response of the request."""

    msg_id = None

    if response.status_code not in [200, 302]:
        # 200 --> OK; 302 --> Found
        # Html page is returned with error description (handling errors same way as on original client. Looks
        # like there is no other way.

        err = re.findall('<td.*?class="errormsg".*?>.*?</td>',
                         response.content.decode('utf-8', 'ignore'),
                         flags=re.DOTALL)

        if len(err) > 0:
            # Remove html tags
            # If part of the message has: Please go  back... remove this part since it is an instruction for
            # the user when using browser.
            err = re.sub('(?:<.*?>)', '', err[0])
            if err:
                raise LogbookMessageRejected('Rejected because of: ' + err)
            else:
                raise LogbookMessageRejected('Rejected because of unknown error.')

        # Other unknown errors
        raise LogbookMessageRejected('Rejected because of unknown error.')
    else:
        location = response.headers.get('Location')
        if location is not None:
            if 'has moved' in location:
                raise LogbookServerProblem('Logbook server has moved to another location.')
            elif 'fail' in location:
                raise LogbookAuthenticationError('Invalid username or password.')
            else:
                # returned locations is something like: '<host>/<sub_dir>/<logbook>/<msg_id><query>
                # with urllib.parse.urlparse returns attribute path=<sub_dir>/<logbook>/<msg_id>
                try:
                    msg_id = int(urllib.parse.urlsplit(location).path.split('/')[-1])
                except ValueError as e:
                    # it was not possible to get the msg_id. 
                    # this may happen when deleting the last entry of a logbook
                    msg_id = None

        if b'type=password' in response.content:
            # Not too smart to check this way, but no other indication of this kind of error.
            # C client does it the same way
            raise LogbookAuthenticationError('Invalid username or password.')

    return response.content, response.headers, msg_id


def _handle_pswd(password, encrypt=True):
    """
    Takes password string and returns password as needed by elog. If encrypt=True then password will be
    sha256 encrypted (salt='', rounds=5000). Before returning password, any trailing $5$$ will be removed
    independent off encrypt flag.

    :param password: password string
    :param encrypt: encrypt password?
    :return: elog prepared password
    """
    if encrypt and password:
        from passlib.hash import sha256_crypt
        return sha256_crypt.using(salt='', rounds=5000).hash(password)[4:]
    elif password and password.startswith('$5$$'):
        return password[4:]
    else:
        return password
