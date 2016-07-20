import http.client
import urllib.parse
import ssl
import os
import copy
from message import Message

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

        self.hostname = hostname
        self.subdir = subdir
        self.logbook = logbook

        if port:
            self.port = port
        else:
            if use_ssl:
                self.port = 443
            else:
                self.port = 80

        self._user = user
        self._password= self.__handle_pswd(password, encrypt_pwd)

        if use_ssl:
            self.server = http.client.HTTPSConnection(hostname, port=port, context=ssl.SSLContext(ssl.PROTOCOL_TLSv1))
        else:
            self.server = http.client.HTTPConnection(hostname, port=port)

        self.content=''  # TODO whats this?


    def post_msg(self, message, msg_id=None, reply=False, attributes=None, attachments=None, encoding='plain', **kwargs):
        '''

        :param message: string with message text or an existing Message()
        :msg_id: Id of message to edit or reply. If not specified new message is created
        :reply: Do reply on existing message (new is created). Else edit existing.
        :param attributes: dictionary of attributes !! Following attributes name are not valid and will be ignored
            because they are used internally by the elog: Text, Date, Encoding, Reply to, In reply to, Locked by,
            Attachment
        :param attachments: list of:
                                  - file like objects which read() will return bytes
                                  - path to the file

                            If there is no attribute flo.name, it will be generated as attributeX.
                            All objects will be appended as attachment to the elog entry.
        :param encoding: can be: 'plain' -> plain text, 'html'->html-text, 'ELCode' --> elog formatting syntax
        :param kwargs: Since there are basically no mandatory fields for logbook(totally depends on the
                       specific logbook configurations) anything in the kwargs will be interpreted as attributes.
                       e.g.: Elog.post_msg('Test text', Author='Rok Vintar), "Author" will be sent as an attribute
                       If named same as one of the attributes defined in "attributes", kwargs will have priority.

        Error handling with exceptions

        :return: Message()
        '''

        # If it is message use its data to post

        new_attributes = copy.copy(attributes)
        new_attchments = copy.copy(attachments)

        if isinstance(message,Message):
            # TODO
            pass
        else:
            #new_attributes = copy.copy(attributes)
            #new_attchments = copy.copy(attachments)

            # Edit existing or post new?
            if msg_id:
                msg_to_edit, attrib_to_edit, attach_to_edit = self.__read_msg_from_server(msg_id)
                # Handle existing attachments
                i = 0
                for attachment in attach_to_edit:
                    if attachment:
                        # Existing attachments must be passed as regular arguments arrachment<i>
                        # TODO New attachment differently
                        attributes['attachment' + str(i)] = attachment
                        i += 1

                # TODO handle **kwargs before this section
                for attribute, data in attributes.items():
                    new_data = attributes.get(attribute)
                    if not new_data is None:
                        attrib_to_edit[attribute] = new_data

            content, headers, boundary = self.__compose_msg(message, attributes, attachments)
            content += self.__param_to_content('edit_id', str(msg_id), boundary)
            content += self.__param_to_content('skiplock', '1', boundary)

        self.__send_msg(content, headers)


    def read_msg(self, msg_id):
        '''
        Reads message from the logbook
        :param msg_id: id of message to read from the logbook
        :return: Message()
        '''
        pass


    def __read_msg_from_server(self, msg_id):
        '''
        Reads message from the logbook server
        TODO docs
        '''
        request_msg = urllib.parse.quote('/' + self.subdir + '/' + self.logbook + '/').replace('//', '/') +\
                       str(msg_id) + '?cmd=download'

        headers =  self.__make_base_headers()

        if self._user or self._password:
            headers['Cookie'] = self.__make_user_and_pswd_cookie()


        self.server.request('GET', request_msg, headers=headers)
        returned_msg = self.server.getresponse().read()
        # TODO check if something to be handled in headers of response

        # returns: message, attributes, attachments
        return(self.__parse_incoming_msg(returned_msg))

    def __compose_msg(self, message, attributes, attachments=list()):
        boundary = b'---------------------------1F9F2F8F3F7F' #TODO randomise boundary
        headers = self.__make_base_headers()
        content = self.__make_base_msg_content(boundary)

        # Clear attributes that are reserved by elog and must not be sent to the server
        self.__remove_reserved_attributes(attributes)

        # Add main message, then append attributes and add attachments
        content += self.__param_to_content ('Text', message, boundary)

        for name, data in attributes.items():
            content += self.__param_to_content (name, data, boundary)

        content += self.__attachments_to_content(attachments, boundary)

        #TODO check what is with this content
        headers['Content-Type'] += '; boundary=' + boundary.decode('utf-8')

        return(content, headers, boundary)

    def __send_msg(self, content, headers):
        request_msg = urllib.parse.quote('/' + self.subdir + '/' + self.logbook + '/').replace('//', '/')
        self.server.request('POST', request_msg , content, headers=headers)
        response_ = self.server.getresponse()

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
        content_ =b''
        newline_= b'\r\n'

        if isinstance(name, str):
            name=name.encode('utf-8')

        if isinstance(data, str):
            data=data.encode('utf-8')

        content_ += boundary + newline_+  b'Content-Disposition: form-data; name=\"' + name + b'\"'

        if kwargs:
            for key_, value_ in kwargs.items():
                content_ += b'; ' + key_.encode('utf-8') + b'=\"' + value_.encode('utf-8') + b'\"'

        if isinstance(data, str):
            data=data.encode('utf-8')

        content_ += newline_ + newline_ + data + b'\r\n' + newline_
        return(content_)

    def __attachments_to_content(self, file_paths, boundary):
        # TODO Fix this to take file like object!
        content = b''
        i = 0
        if file_paths:
            for file_path in file_paths:
                i += 1
                file = open(file_path, 'rb')
                content += self.__param_to_content('attfile' + str(i), file.read(), boundary,
                                                  filename=os.path.basename(file_path))
                file.close()

        return(content)

    ## Not jet
    def __parse_incoming_msg(self, msg):
        attributes = dict()
        attachments = list()

        msg = msg.decode('utf-8').splitlines()
        delimeter_idx = msg.index('========================================')

        message = '\n'.join(msg[delimeter_idx+1:])
        for line in msg[0:delimeter_idx]:
            line = line.split(': ')
            data = ''.join(line[1:])
            if line[0] == 'Attachment':
                attachments = data.split(',')
            else:
                attributes[line[0]] = data

        return(message, attributes, attachments)

    def __remove_reserved_attributes(self, attributes):
        # Delete attributes that cannot be sent (reserved by elog)
        # TODO check if something to add to this list
        if attributes.get('$@MID@$'):
            del attributes['$@MID@$']
        if attributes.get('Date'):
            del attributes['Date']
        if attributes.get('Attachment'):
            del attributes['Attachment']

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
