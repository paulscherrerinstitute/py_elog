import http.client
import urllib.parse
import ssl
import os

class Elog(object):
    def __init__(self, hostname, port=None, use_ssl=True, subdir='', user=None, password=None, encrypt=True, debug=0):
        self.subdir = subdir
        self.hostname = hostname
        self.port = port
        self.user = user
        self.password= self.handle_pswd_(password, encrypt)

        if use_ssl:
            self.server = http.client.HTTPSConnection(hostname, port=port, context=ssl.SSLContext(ssl.PROTOCOL_TLSv1))
        else:
            self.server = http.client.HTTPConnection(hostname, port=port)
            self.server = http.client.HTTPConnection(hostname, port=port)

        self.server.set_debuglevel(debug)
        self.content=''

    def get_msg(self, logbook, msg_id):
        request_msg_ = urllib.parse.quote('/' + self.subdir + '/' + logbook + '/').replace('//', '/') +\
                       str(msg_id) + '?cmd=download'

        headers_ =  self.make_base_headers_()

        if self.user or self.password:
            headers_['Cookie'] = self.make_user_and_pswd_cookie_()


        self.server.request('GET', request_msg_, headers=headers_)
        msg = self.server.getresponse().read()

        msg = self.parse_incoming_msg_(msg)
        return(msg)

    def add_msg(self, logbook, msg, attachments=list()):
        # 'Text'  --> log/body text
        # Other settings (some may be mandatory) ... each key is one setting, like 'Author', etc.
        # attachments --> list of files to attach
        content, headers, boundary = self.compose_msg_(logbook, msg, attachments)
        self.post_msg_(logbook, content, headers)


    def edit_msg(self, logbook, msg_id, msg, attachments=list(), keep_existing=True):
        # keep_existing:
        #                True:  Attributes not defined in "msg" and existing attachments will be preserved.
        #                False: Attributes not defined in "msg" and existing attachments will be deleted.
        # 1. Get message
        # 2. Replace/add msg items with new
        # 3. Post message

        if keep_existing:
            msg_to_edit = self.get_msg(logbook, msg_id)

            # Handle existing attachments
            i = 0
            for attachment in msg_to_edit["Attachment"]:
                if attachment:
                    msg_to_edit['attachment' + str(i)] = attachment
                    i += 1

            print(msg_to_edit)

            for name, data in msg_to_edit.items():
                new_data = msg.get(name)
                if not new_data is None:
                    msg_to_edit[name] = new_data
        else:
            msg_to_edit = msg

        print(msg_to_edit)
        content, headers, boundary = self.compose_msg_(logbook, msg_to_edit, attachments)
        content += self.param_to_content_('edit_id', str(msg_id), boundary)
        content += self.param_to_content_('skiplock', '1', boundary)
        self.post_msg_(logbook, content, headers)

    def reply_to_msg(self, logbook, msg_id, msg, attachments=list()):
        #    def reply_on_message(self, msg_id):
        #        self.param_to_content_('reply_to', msg_id)
        content, headers, boundary = self.compose_msg_(logbook, msg, attachments)
        content += self.param_to_content_('reply_to', str(msg_id), boundary)
        self.post_msg_(logbook, content, headers)

    def compose_msg_(self, logbook, msg, attachments=list()):
        boundary = b'---------------------------1F9F2F8F3F7F'
        content = self.make_base_msg_content_(logbook, boundary)

        self.remove_reserved_attributes_(msg)

        for name, data in msg.items():
            content += self.param_to_content_ (name, data, boundary)

        content += self.attachments_to_content_(attachments, boundary)

        headers = self.make_base_headers_()
        headers['Content-Type'] += '; boundary=' + boundary.decode('utf-8')

        return(content, headers, boundary)

    def post_msg_(self, logbook, content, headers):
        request_msg = urllib.parse.quote('/' + self.subdir + '/' + logbook + '/').replace('//', '/')
        self.server.request('POST', request_msg , content, headers=headers)
        response_ = self.server.getresponse().read()

    def make_base_headers_(self):
        header = dict()
        header['User-Agent'] = 'ELOG'
        header['Content-Type'] = 'multipart/form-data'

        return(header)

    def make_base_msg_content_(self, logbook, boundary):
        content = self.param_to_content_('cmd', 'Submit', boundary)
        content += self.param_to_content_('exp', logbook, boundary)
        if self.user:
            content += self.param_to_content_('unm', self.user, boundary)
        if self.password:
            content += self.param_to_content_('upwd', self.password, boundary)

        return(content)

    def param_to_content_ (self, name, data, boundary, **kwargs):
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

    def attachments_to_content_(self, file_paths, boundary):
        content = b''
        i = 0
        for file_path in file_paths:
            i += 1
            file = open(file_path, 'rb')
            content += self.param_to_content_('attfile' + str(i), file.read(), boundary,
                                              filename=os.path.basename(file_path))
            file.close()

        return(content)

    def parse_incoming_msg_(self, msg):
        attributes = dict()

        msg = msg.decode('utf-8').splitlines()
        delimeter_idx = msg.index('========================================')

        attributes['Text'] = '\n'.join(msg[delimeter_idx+1:])
        for line in msg[0:delimeter_idx]:
            line = line.split(': ')
            data = ''.join(line[1:])
            if line[0] == 'Attachment':
                data = data.split(',')

            attributes[line[0]] = data

        return(attributes)

    def remove_reserved_attributes_(self, msg):
        # Delete attributes that cannot be sent (reserved by elog)
        if msg.get('$@MID@$'):
            del msg['$@MID@$']
        if msg.get('Date'):
            del msg['Date']
        if msg.get('Attachment'):
            del msg['Attachment']

    def make_user_and_pswd_cookie_(self):
        cookie=''
        if self.user:
            cookie += 'unm=' + self.user + ';'
        if self.password:
            cookie += 'upwd=' + self.password + ';'

        return(cookie)

    def handle_pswd_(self, password, encrypt=True):
        if encrypt and password:
            from passlib.hash import sha256_crypt
            return(sha256_crypt.encrypt(password, salt='', rounds=5000)[4:])
        elif password and password.startswith('$5$$'):
            return(password[4:])
        else:
            return(password)


    def validate_response_(response):
            if response.startswith(b'<!DOCTYPE html>'):
               raise PermissionError('Invalid username and password.')
            else:
                return(response)




#elog_dia = Elog('diagnostics-elog.psi.ch', user='VR84', password='Mige9GgiQax3jSkTB84Pjrt3FynXDD5KyFSktg7GWwB', encrypt=False, debug=1)
#response = elog_dia.get_msg('DB-SwissFEL-Inst-DWSC', 28)

#elog_midas = Elog('midas.psi.ch', subdir='elogs', port=None, use_ssl=False, debug=1)
#response = elog_midas.get_msg('Linux Demo', 7)

#elog_lh = Elog('localhost', subdir='', port=8080, use_ssl=False, debug=0)
#response = elog_lh.get_msg('Rok', 1)


#data = dict()
#data['Text'] ='''Lorem Ipusm Repolaces
#Replaced
#
#'''
#data['Author'] = 'BLumen'
#data['Subject'] = 'Lumen'


#msg = elog_lh.new_msg('Rok', data)
#msg = elog_lh.get_msg('Rok', 24)
#msg = elog_lh.edit_msg('Rok', 17, data)
#msg = elog_lh.reply_to_msg('Rok', 22, data)
#print(msg)

#print(response.decode(encoding='utf-8'))

