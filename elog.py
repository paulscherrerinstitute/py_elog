import http.client
import urllib.parse
import ssl
import os

class Logbook(object):
    '''
    Logbook: server:port/subdir/logbook

    Logbook object holds a list of existing Message() instances. If post_msg is called and message with msg_id
    already exists it will be updated and returned.
    '''
    def __init__(self, hostname, logbook, port=None, user=None, password=None, subdir='', use_ssl=True,
                 encrypt_pwd=True):
        '''
        :param hostname: elog server hostname
        :param logbook: name of the logbook on the elog server
        :param port: elog server port (if not specified will default to '80' if use_ssl=False or '443' if use_ssl=True
        :param user: username (if authentication needed)
        :param password: password (if authentication needed)
        :param subdir: subdirectory of logbooks locations
        :param use_ssl: connect using ssl?
        :param encrypt_pwd: To avoid exposing password in the code, this flag can be set to False and password
                            will be then handled as it is (user needs to provide sha256 encrypted password with
                            salt= '' and rounds=5000)
        :return:
        '''
        self.logbook = logbook

        self._user = user
        self._password= self.__handle_pswd(password, encrypt_pwd)

        self._logbook_path = urllib.parse.quote('/' + subdir + '/' + logbook + '/').replace('//', '/')

        if port:
            url = hostname + ':' + str(port)
        else:
            url = hostname

        if use_ssl:
            self.server = http.client.HTTPSConnection(hostname, port=port, context=ssl.SSLContext(ssl.PROTOCOL_TLSv1))
            self._url =  'https://' + url + self._logbook_path
        else:
            self.server = http.client.HTTPConnection(hostname, port=port)
            self._url =  'http://' + url + self._logbook_path

    def post_msg(self, message, msg_id=None, reply=False, attributes=None, attachments=None, encoding='plain',
                 **kwargs):
        '''

        :param message: string with message text or an existing Message()
        :msg_id: Id of message to edit or reply. If not specified new message is created
        :reply: Do reply on existing message (new is created). Else edit existing.
        :param attributes: dictionary of attributes !! Following attributes name are not valid and will be ignored
            because they are used internally by the elog: Text, Date, Encoding, Reply to, In reply to, Locked by,
            Attachment
        :param attachments: list of:
                                  - file like objects which read() will return bytes

                            If there is no attribute flo.name, it will be generated as attributeX.
                            All objects will be appended as attachment to the elog entry.
        :param encoding: can be: 'plain' -> plain text, 'html'->html-text, 'ELCode' --> elog formatting syntax
        :param kwargs: Since there are basically no mandatory fields for logbook(totally depends on the
                       specific logbook configurations) anything in the kwargs will be interpreted as attributes.
                       e.g.: Elog.post_msg('Test text', Author='Rok Vintar), "Author" will be sent as an attribute
                       If named same as one of the attributes defined in "attributes", kwargs will have priority.

        Error handling with exceptions

        :return: msg_id
        '''

        attributes = attributes or {}
        attributes = {**attributes, **kwargs} # kwargs as attributes with higher priority

        attachments = attachments or []

        if msg_id and reply: # Reply to
            attributes['reply_to'] = str(msg_id)

        elif msg_id: # Edit existing
            attributes['edit_id'] = str(msg_id)
            attributes['skiplock'] = '1'

            # Handle existing attachments
            msg_to_edit, attrib_to_edit, attach_to_edit = self.read_msg(msg_id)
            i = 0
            for attachment in attach_to_edit:
                if attachment:
                    # Existing attachments must be passed as regular arguments attachment<i> with walue= file name
                    # Read message returnes full urls to existing attachments:
                    # <hostename>:[<port>][/<subdir]/<logbook>/<msg_id>/<file_name>
                    attributes['attachment' + str(i)] = os.path.basename(attachment)
                    i += 1

            for attribute, data in attributes.items():
                new_data = attributes.get(attribute)
                if not new_data is None:
                    attrib_to_edit[attribute] = new_data

        content, headers, boundary = self.__compose_msg(message, attributes, attachments)
        response = self.__send_msg(content, headers)

        for header in response.getheaders():
            if header[0] == 'Location':
                # Successfully posted. Get and return msg_id from response
                return(int(header[1].split('/')[-1]))
            #else:
                # else Todo raise custom exception

    def read_msg(self, msg_id):
        '''
        Reads message from the logbook server
        TODO docs
        '''
        # First build request, then parse response
        request_msg = self._logbook_path +str(msg_id) + '?cmd=download'

        request_headers =  self.__make_base_headers()

        if self._user or self._password:
            request_headers['Cookie'] = self.__make_user_and_pswd_cookie()


        self.server.request('GET', request_msg, headers=request_headers)
        response = self.server.getresponse()
        # TODO error handling


        # Parse message to separate message body, attributes and attachments
        attributes = dict()
        attachments = list()

        returned_msg = response.read().decode('utf-8').splitlines()
        delimeter_idx = returned_msg.index('========================================')

        message = '\n'.join(returned_msg[delimeter_idx+1:])
        for line in returned_msg[0:delimeter_idx]:
            line = line.split(': ')
            data = ''.join(line[1:])
            if line[0] == 'Attachment':
                attachments = data.split(',')
                # Here are only attachment names, make a full url out of it, so they could be
                # recognisable by others, and downloaded if needed
                attachments = [self._url+ '{0}'.format(i) for i in attachments]
            else:
                attributes[line[0]] = data

        return(message, attributes, attachments)

    def delete_msg(self, msg_id):
        '''
        Deletes message from logbook. It also deletes all of the attachments.

        :param msg_id: message to be deleted
        :return:
        '''
        request_msg = self._logbook_path +str(msg_id) + '?cmd=Delete&confirm=Yes'
        request_headers =  self.__make_base_headers()

        if self._user or self._password:
            request_headers['Cookie'] = self.__make_user_and_pswd_cookie()


        self.server.request('GET', request_msg, headers=request_headers)
        response = self.server.getresponse()
        # TODO error handling



    def __compose_msg(self, message, attributes, attachments):
        boundary = b'---------------------------1F9F2F8F3F7F' #TODO randomise boundary
        headers = self.__make_base_headers()
        content = self.__make_base_msg_content(boundary)

        # Clear attributes that are reserved by elog and must not be sent to the server
        self.__remove_reserved_attributes(attributes)

        # Add main message, then append attributes and add attachments
        content += self.__param_to_content ('Text', message, boundary)
        if attributes:
            for name, data in attributes.items():
                content += self.__param_to_content (name, data, boundary)

        if attachments:
            content += self.__attachments_to_content(attachments, boundary)

        content += boundary
        # from __make_base_header set Content-Type: multipart/form-data
        headers['Content-Type'] += '; boundary=' + boundary.decode('utf-8')
        return(content, headers, boundary)

    def __send_msg(self, content, headers):
        self.server.request('POST', self._logbook_path , content, headers=headers)
        response = self.server.getresponse()

        return(response)

    def __make_base_headers(self):
        header = dict()
        header['User-Agent'] = 'ELOG'
        header['Content-Type'] = 'multipart/form-data'

        return(header)

    def __make_base_msg_content(self, boundary):
        content = self.__param_to_content('cmd', 'Submit', boundary)
        content += self.__param_to_content('exp', self.logbook, boundary)
        if self._user:
            content += self.__param_to_content('unm', self._user, boundary)
        if self._password:
            content += self.__param_to_content('upwd', self._password, boundary)

        return(content)

    def __param_to_content (self, name, data, boundary, **kwargs):
        content =b''
        newline= b'\r\n'

        if isinstance(name, str):
            name = name.encode('utf-8')

        if isinstance(data, str):
            data = data.encode('utf-8')

        content += boundary + newline +  b'Content-Disposition: form-data; name=\"' + name + b'\"'

        if kwargs:
            for key_, value_ in kwargs.items():
                content += b'; ' + key_.encode('utf-8') + b'=\"' + value_.encode('utf-8') + b'\"'

        if isinstance(data, str):
            data = data.encode('utf-8')

        content += newline + newline + data + b'\r\n' + newline

        return(content)

    def __attachments_to_content(self, files, boundary):
        content = b''
        i = 0
        for file_obj in files:
            if hasattr(file_obj, 'read'):
                i += 1
                attribute_name = 'attfile' + str(i)

                filename = attribute_name  # If file like object has no name specified use this one
                candidate_filename = os.path.basename(file_obj.name)

                if filename: # use only if not empty string
                    filename = candidate_filename

                content += self.__param_to_content(attribute_name, file_obj.read(), boundary, filename=filename)

            else:
                raise TypeError('Attachment[' + str(i) + '] is not a file like object. Cannot be read.')

        return(content)

    def __remove_reserved_attributes(self, attributes):
        # Delete attributes that cannot be sent (reserved by elog)

        if attributes:
            attributes.get('$@MID@$', None)
            attributes.pop('Date', None)
            attributes.pop('Attachment', None)
            attributes.pop('Text', None)
            attributes.pop('Encoding', None)
            attributes.pop('Locked by', None)
            attributes.pop('In reply to', None)
            attributes.pop('Reply to', None)

    def __make_user_and_pswd_cookie(self):
        cookie=''
        if self._user:
            cookie += 'unm=' + self._user + ';'
        if self._password:
            cookie += 'upwd=' + self._password + ';'

        return(cookie)

    def __handle_pswd(self, password, encrypt=True):
        '''
        Takes password string and returns password as needed by elog. If encrypt=True then password will be
        sha256 encrypted (salt='', rounds=5000). Before returning password, any trailing $5$$ will be removed
        independent off encrypt flag.

        :param password: password string
        :param encrypt: encrypt password?
        :return: elog prepared password
        '''
        if encrypt and password:
            from passlib.hash import sha256_crypt
            return(sha256_crypt.encrypt(password, salt='', rounds=5000)[4:])
        elif password and password.startswith('$5$$'):
            return(password[4:])
        else:
            return(password)

def open(*args, **kwargs):
    return(Logbook(*args, **kwargs))