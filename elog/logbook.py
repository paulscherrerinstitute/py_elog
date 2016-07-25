import requests
import urllib.parse
import os
import builtins
import re
from elog.logbook_exceptions import *


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
        :param use_ssl: connect using ssl?
        :param encrypt_pwd: To avoid exposing password in the code, this flag can be set to False and password
                            will then be handled as it is (user needs to provide sha256 encrypted password with
                            salt= '' and rounds=5000)
        :return:
        """

        # handle if logbook is url
        if hostname.startswith('http'):
            self._url = hostname
            url_parsed = urllib.parse.urlparse(hostname)

            use_ssl = (url_parsed == 'https')  # else is http
            net_location = url_parsed.netloc.split(':')
            hostname = net_location[0]
            if len(net_location) > 1:
                port = net_location[1]
            else:
                port = None

            self._logbook_path = url_parsed.path
            # logbook is the last in url_parsed.path everything before is a subdir
            url_path = url_parsed.path[1:]  # remove trailing /
            if url_path.endswith('/'):
                url_path = url_path[:-1]

            url_path = url_path.split('/')

            self.logbook = url_path[-1]

        else:
            self.logbook = logbook
            self._logbook_path = urllib.parse.quote('/' + subdir + '/' + logbook + '/').replace('//', '/')

            if port or (port == 80 and not use_ssl) or (port == 443 and use_ssl):
                url = hostname + ':' + str(port)
            else:
                url = hostname

            if use_ssl:
                self._url = 'https://' + url + self._logbook_path
            else:
                self._url = 'http://' + url + self._logbook_path

        self._user = user
        self._password = self.__handle_pswd(password, encrypt_pwd)

    def post_msg(self, message, msg_id=None, reply=False, attributes=None, attachments=None, encoding='plain',
                 **kwargs):
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
        :param kwargs: Anything in the kwargs will be interpreted as attribute. e.g.: logbook.post_msg('Test text',
                       Author='Rok Vintar), "Author" will be sent as an attribute. If named same as one of the
                       attributes defined in "attributes", kwargs will have priority.

        :return: msg_id
        """

        attributes = attributes or {}
        attributes = {**attributes, **kwargs}  # kwargs as attributes with higher priority

        attachments = attachments or []

        if encoding not in ['plain', 'HTML', 'ELCode']:
            raise LogbookMessageRejected('Invalid message encoding. Valid options: plain, HTML, ELCode.')

        attributes['encoding'] = encoding
        attributes_to_edit = dict()
        if msg_id:
            # Message exists, we can continue
            if reply:
                # Verify that there is a message on the server, otherwise do not reply or reply to it!
                self.__check_if_message_on_server(msg_id)  # raises exception in case of none existing message

                attributes['reply_to'] = str(msg_id)

            else:  # Edit existing
                attributes['edit_id'] = str(msg_id)
                attributes['skiplock'] = '1'

                # Handle existing attachments
                msg_to_edit, attributes_to_edit, attach_to_edit = self.read_msg(msg_id)

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

        if not attributes_to_edit:
            attributes_to_edit = attributes
        # Remove any attributes that should not be sent
        self.__remove_reserved_attributes(attributes_to_edit)

        if attachments:
            files_to_attach = self.__prepare_attachments(attachments)
        else:
            files_to_attach = list()

        # Make requests module think that Text is a "file". This is the only way to force requests to send data as
        # multipart/form-data even if there are no attachments. Elog understands only multipart/form-data
        files_to_attach.append(('Text', ('', message)))

        # Base attributes are common to all messages
        self.__add_base_msg_attributes(attributes_to_edit)

        try:
            response = requests.post(self._url, data=attributes_to_edit, files=files_to_attach, allow_redirects=False,
                                     verify=False)
            # Validate response. Any problems will raise an Exception.
            resp_message, resp_headers, resp_msg_id = self.__validate_response(response)

            # Close file like objects
            for attachment in files_to_attach:
                if hasattr(attachment, 'close'):
                    attachment.close()

        except requests.RequestException as e:
            # This means there were no response on download command. Check if message on server.
            self.__check_if_message_on_server(msg_id)  # raises exceptions if no message or no response from server

            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to post a message, ' + 'because of:\n' +
                                       '{0}'.format(e))

        # Any error before here should raise an exception, but check again for nay case.
        if not resp_msg_id or resp_msg_id < 1:
            raise LogbookInvalidMessageID('Invalid message ID: ' + str(resp_msg_id) + ' returned')
        return(resp_msg_id)

    def read_msg(self, msg_id):
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
            request_headers['Cookie'] = self.__make_user_and_pswd_cookie()

        try:
            self.__check_if_message_on_server(msg_id)  # raises exceptions if no message or no response from server
            response = requests.get(self._url + str(msg_id) + '?cmd=download', headers=request_headers,
                                    allow_redirects=False, verify=False)

            # Validate response. If problems Exception will be thrown.
            resp_message, resp_headers, resp_msg_id = self.__validate_response(response)

        except requests.RequestException as e:
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to read the message with ID: ' + str(msg_id) +
                                       'because of:\n' + '{0}'.format(e))

        # Parse message to separate message body, attributes and attachments
        attributes = dict()
        attachments = list()

        returned_msg = resp_message.decode('utf-8').splitlines()
        delimiter_idx = returned_msg.index('========================================')

        message = '\n'.join(returned_msg[delimiter_idx + 1:])
        for line in returned_msg[0:delimiter_idx]:
            line = line.split(': ')
            data = ''.join(line[1:])
            if line[0] == 'Attachment':
                attachments = data.split(',')
                # Here are only attachment names, make a full url out of it, so they could be
                # recognisable by others, and downloaded if needed
                attachments = [self._url + '{0}'.format(i) for i in attachments]
            else:
                attributes[line[0]] = data

        return(message, attributes, attachments)

    def delete_msg_thread(self, msg_id):
        """
        Deletes message thread (!!!message + all replies!!!) from logbook.
        It also deletes all of attachments of corresponding messages from the server.

        :param msg_id: message to be deleted
        :return:
        """

        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self.__make_user_and_pswd_cookie()

        try:
            response = requests.get(self._url + str(msg_id) + '?cmd=Delete&confirm=Yes', headers=request_headers,
                                    allow_redirects=False, verify=False)
            self.__validate_response(response)
        except requests.RequestException as e:
            # This means there were no response on download command. Check if message on server.
            self.__check_if_message_on_server(
                msg_id)  # raises exceptions when missing message or no response from server
            # If here: message is on server but cannot be downloaded (should never happen)
            raise LogbookServerProblem('Cannot access logbook server to delete the message with ID: ' + str(msg_id) +
                                       'because of:\n' + '{0}'.format(e))

    def __check_if_message_on_server(self, msg_id):
        """Try to load page for specific message. If there is text 'This entry has been deleted' on the page,
        message has been deleted or not yet created.

        :param msg_id: ID of message to be checked
        :return:
        """

        request_headers = dict()
        if self._user or self._password:
            request_headers['Cookie'] = self.__make_user_and_pswd_cookie()
        try:
            response = requests.get(self._url + str(msg_id), headers=request_headers, allow_redirects=False,
                                    verify=False)
            # Validate response. If problems Exception will be thrown.
            resp_message, resp_headers, resp_msg_id = self.__validate_response(response)
            if b'This entry has been deleted' in resp_message:
                raise LogbookInvalidMessageID('Message with ID: ' + str(msg_id) + ' does not exist on logbook.')

        except requests.RequestException as e:
            raise LogbookServerProblem('No response from the logbook server.\nDetails: ' + '{0}'.format(e))

    def __add_base_msg_attributes(self, data):
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

    def __prepare_attachments(self, files):
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

                if os.path.isfile(file_obj):
                    i += 1
                    attribute_name = 'attfile' + str(i)

                    file_obj = builtins.open(file_obj, 'rb')
                    filename = os.path.basename(file_obj.name)

                elif not file_obj.startswith(self._url):
                    raise LogbookInvalidAttachmentType('Invalid type of attachment: \"' + file_obj + '\".')
            else:
                raise LogbookInvalidAttachmentType('Invalid type of attachment[' + str(i) + '].')

            prepared.append((attribute_name, (filename, file_obj)))

        return(prepared)

    def __remove_reserved_attributes(self, attributes):
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
            attributes.pop('Encoding', None)

    def __make_user_and_pswd_cookie(self):
        """
        prepares user name and password cookie. It is sent in header when posting a message.
        :return: user name and password value for the Cookie header
        """
        cookie = ''
        if self._user:
            cookie += 'unm=' + self._user + ';'
        if self._password:
            cookie += 'upwd=' + self._password + ';'

        return(cookie)

    def __validate_response(self, response):
        """ Validate response of the request."""

        msg_id = None

        if response.status_code not in [200, 302]:
            # 200 --> OK; 302 --> Found
            # Html page is returned with error description (handling errors same way as on original client. Looks
            # like there is no other way.

            err = re.findall('Error:.*?</td>', response.content.decode('utf-8'), flags=re.DOTALL)

            if len(err) > 0:
                # Remove html tags
                # If part of the message has: Please go  back... remove this part since it is an instruction for
                # the user when using browser.
                err = re.sub('(?:<.*?>|Please go back.*)', '', err[0])
                if err:
                    raise LogbookMessageRejected('Rejected because of: ' + err)
            # Other unknown errors
            raise LogbookMessageRejected('Rejected because of unknown error')
        else:
            location = response.headers.get('Location')
            if location is not None:
                if 'has moved' in location:
                    raise LogbookServerProblem('Logbook server has moved to another location.')
                elif 'fail' in location:
                    raise LogbookAuthenticationError('Invalid username or password.')
                else:
                    msg_id = int(location.split('/')[-1])

                if b'form name=form1' in response.content or b'enter password' in response.content:
                    # Not to smart to check this way, but no other indication of this kind of error.
                    # C client does it the same way
                    raise LogbookAuthenticationError('Invalid username or password.')

        return(response.content, response.headers, msg_id)

    def __handle_pswd(self, password, encrypt=True):
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
            return(sha256_crypt.encrypt(password, salt='', rounds=5000)[4:])
        elif password and password.startswith('$5$$'):
            return(password[4:])
        else:
            return(password)
