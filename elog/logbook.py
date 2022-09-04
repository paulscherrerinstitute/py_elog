import requests
import urllib.parse
import os
import builtins
import re
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
             suppress_email_notification=False, encoding=None, **kwargs):
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
        :param encoding: Defines encoding of the message. Can be: 'plain' -> plain text, 'html'->html-text,
                         'ELCode' --> elog formatting syntax
        :param suppress_email_notification: If set to True or 1, E-Mail notification will be suppressed, defaults to False.
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

        if suppress_email_notification != False:
            attributes["suppress"] = 1


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

                # Handle existing attachments
                msg_to_edit, attributes_to_edit, attach_to_edit = self.read(msg_id)

                i = 0
                for attachment in attach_to_edit:
                    if attachment:
                        # Existing attachments must be passed as regular arguments attachment<i> with value= file name
                        # Read message returnes full urls to existing attachments:
                        # <hostname>:[<port>][/<subdir]/<logbook>/<msg_id>/<file_name>
                        attributes['attachment' + str(i)] = os.path.basename(attachment)
                        i += 1

                for attribute, data in attributes.items():
                    new_data = attributes.get(attribute)
                    if new_data is not None:
                        attributes_to_edit[attribute] = new_data
        else:
            # As we create a new message, specify creation time if not already specified in attributes
            if 'When' not in attributes:
                attributes['When'] = int(datetime.now().timestamp())

        if not attributes_to_edit:
            attributes_to_edit = attributes
        # Remove any attributes that should not be sent
        _remove_reserved_attributes(attributes_to_edit)

        if attachments:
            files_to_attach, objects_to_close = self._prepare_attachments(attachments)
        else:
            objects_to_close = list()
            files_to_attach = list()

        # Make requests module think that Text is a "file". This is the only way to force requests to send data as
        # multipart/form-data even if there are no attachments. Elog understands only multipart/form-data
        files_to_attach.append(('Text', ('', message.encode('iso-8859-1'))))

        # Base attributes are common to all messages
        self._add_base_msg_attributes(attributes_to_edit)
        
        # Keys in attributes cannot have certain characters like whitespaces or dashes for the http request
        attributes_to_edit = _replace_special_characters_in_attribute_keys(attributes_to_edit)
        
        # All string values in the attributes must be encoded in latin1
        attributes_to_edit = _encode_values(attributes_to_edit)

        try:
            response = requests.post(self._url, data=attributes_to_edit, files=files_to_attach, allow_redirects=False,
                                     verify=False)
            
            # Validate response. Any problems will raise an Exception.
            resp_message, resp_headers, resp_msg_id = _validate_response(response)

            # Close file like objects that were opened by the elog (if  path
            for file_like_object in objects_to_close:
                if hasattr(file_like_object, 'close'):
                    file_like_object.close()

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

    def read(self, msg_id):
        """
        Reads message from the logbook server and returns tuple of (message, attributes, attachments) where:
        message: string with message body
        attributes: dictionary of all attributes returned by the logbook
        attachments: list of urls to attachments on the logbook server

        :param msg_id: ID of the message to be read
        :return: message, attributes, attachments
        """

        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()

        try:
            self._check_if_message_on_server(msg_id)  # raises exceptions if no message or no response from server
            response = requests.get(self._url + str(msg_id) + '?cmd=download', headers=request_headers,
                                    allow_redirects=False, verify=False)

            # Validate response. If problems Exception will be thrown.
            resp_message, resp_headers, resp_msg_id = _validate_response(response)

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

    def delete(self, msg_id):
        """
        Deletes message thread (!!!message + all replies!!!) from logbook.
        It also deletes all of attachments of corresponding messages from the server.

        :param msg_id: message to be deleted
        :return:
        """

        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()

        try:
            self._check_if_message_on_server(msg_id)  # check if something to delete

            response = requests.get(self._url + str(msg_id) + '?cmd=Delete&confirm=Yes', headers=request_headers,
                                    allow_redirects=False, verify=False)

            _validate_response(response)  # raises exception if any other error identified

        except requests.RequestException as e:
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to delete the message with ID: ' + str(msg_id) +
                                       'because of:\n' + '{0}'.format(e))

        # Additional validation: If successfully deleted then status_code = 302. In case command was not executed at
        # all (not English language --> no download command supported) status_code = 200 and the content is just a
        # html page of this whole message.
        if response.status_code == 200:
            raise LogbookServerProblem('Cannot process delete command (only logbooks in English supported).')

    def search(self, search_term, n_results=20, scope="subtext"):
        """
        Searches the logbook and returns the message ids.

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
                                    allow_redirects=False, verify=False)

            # Validate response. If problems Exception will be thrown.
            _validate_response(response)
            resp_message = response

        except requests.RequestException as e:
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to read message ids '
                                       'because of:\n' + '{0}'.format(e))

        from lxml import html
        tree = html.fromstring(resp_message.content)
        message_ids = tree.xpath('(//tr/td[@class="list1" or @class="list2"][1])/a/@href')
        message_ids = [int(m.split("/")[-1]) for m in message_ids]
        return message_ids

    def get_last_message_id(self):
        ids = self.get_message_ids()
        if len(ids) > 0:
            return ids[0]
        else:
            return None

    def get_message_ids(self):
        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()

        try:
            response = requests.get(self._url + 'page', headers=request_headers,
                                    allow_redirects=False, verify=False)

            # Validate response. If problems Exception will be thrown.
            _validate_response(response)
            resp_message = response

        except requests.RequestException as e:
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to read message ids '
                                       'because of:\n' + '{0}'.format(e))

        from lxml import html
        tree = html.fromstring(resp_message.content)
        message_ids = tree.xpath('(//tr/td[@class="list1" or @class="list2"][1])/a/@href')
        message_ids = [int(m.split("/")[-1]) for m in message_ids]
        return message_ids

    def _check_if_message_on_server(self, msg_id):
        """Try to load page for specific message. If there is a htm tag like <td class="errormsg"> then there is no
        such message.

        :param msg_id: ID of message to be checked
        :return:
        """

        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self._make_user_and_pswd_cookie()
        try:
            response = requests.get(self._url + str(msg_id), headers=request_headers, allow_redirects=False,
                                    verify=False)

            # If there is no message code 200 will be returned (OK) and _validate_response will not recognise it
            # but there will be some error in the html code.
            resp_message, resp_headers, resp_msg_id = _validate_response(response)
            # If there is no message, code 200 will be returned (OK) but there will be some error indication in
            # the html code.
            if re.findall('<td.*?class="errormsg".*?>.*?</td>',
                          resp_message.decode('utf-8', 'ignore'),
                          flags=re.DOTALL):
                raise LogbookInvalidMessageID('Message with ID: ' + str(msg_id) + ' does not exist on logbook.')

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

        Note that if attachment is is an url pointing to the existing Logbook server it will be ignored and no
        exceptions will be raised. This can happen if attachments returned with read_method are resend.

        :param files: list of file like objects or paths
        :return: content string
        """
        prepared = list()
        i = 0
        objects_to_close = list()  # objects that are created (opened) by elog must be later closed
        for file_obj in files:
            if hasattr(file_obj, 'read'):
                i += 1
                attribute_name = 'attfile' + str(i)

                filename = attribute_name  # If file like object has no name specified use this one
                candidate_filename = os.path.basename(file_obj.name)

                if filename:  # use only if not empty string
                    filename = candidate_filename

            elif isinstance(file_obj, str):
                # Check if it is:
                #           - a path to the file --> open file and append
                #           - an url pointing to the existing Logbook server --> ignore

                filename = ""
                attribute_name = ""

                if os.path.isfile(file_obj):
                    i += 1
                    attribute_name = 'attfile' + str(i)

                    file_obj = builtins.open(file_obj, 'rb')
                    filename = os.path.basename(file_obj.name)

                    objects_to_close.append(file_obj)

                elif not file_obj.startswith(self._url):
                    raise LogbookInvalidAttachmentType('Invalid type of attachment: \"' + file_obj + '\".')
            else:
                raise LogbookInvalidAttachmentType('Invalid type of attachment[' + str(i) + '].')

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

        if b'form name=form1' in response.content or b'type=password' in response.content:
            # Not to smart to check this way, but no other indication of this kind of error.
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
