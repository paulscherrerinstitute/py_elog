# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
import os.path

import elog

def generate_all_attachment_files(file_dict):
    for filename, content in file_dict.items():
        generate_attachment_file(filename, content)


def generate_attachment_file(filename, content):
    with open(filename,'w') as file:
        file.write(content)

def main():

    # create the two attachment files
    attachment_file_dict ={
        'attach1.txt' : 'Content of the first file',
        'attach2.txt' : 'Another file with another content'
    }
    print('Generating all attachments', end='')
    generate_all_attachment_files(attachment_file_dict)
    attachment_list = [key for key in attachment_file_dict]
    print('........ DONE!')

    elog_hostname = 'http://localhost:8080/Quattro-Analysis'
    user = 'log-robot'
    psw = 'IchBinRoboter'
    logbook = elog.open(elog_hostname, user=user,password=psw)

    print('Removing all entries', end='')
    for id in logbook.get_message_ids():
        logbook.delete(id)
    print('........ DONE!')

    attributes = {'Operator': 'Ich', 'Protocol ID': 'AAA', 'Project':'BBB', 'Customer':'CCC'}

    print('Attempting to post a new message with some attachments. All attachments are freshly uploaded', end='')
    msg_id = logbook.post('This post has all the attachments freshly uploaded by the user', attributes=attributes,
                          attachments=attachment_list)
    print('........ DONE!')

    print('Reading back the logbook entry', end='')
    msg, attrs, attachs =    logbook.read(msg_id)
    print('........ DONE!')
    print('Those are the attachments on the server')
    for attach in attachs:
        print(f' --> {attach}')


    # print('Attempting to post a modified post with the same attachments. The exisisting attachment will be reused', end='')
    # msg_id = logbook.post('Modified post. Check the logbook folder, there should be only one copy of each attachment file with the original timestamp', attributes=attributes, attachments=attachment_list,msg_id=msg_id)
    # print('........ DONE!')
    #
    # print('Reading back the logbook entry', end='')
    # msg, attrs, attachs2 = logbook.read(msg_id)
    # print('........ DONE!')
    # if attachs2 == attachs:
    #     print('Verified attachment timestamps are OK.')
    # else:
    #     print('Something did not work!')
    #
    #
    # print('Attempting to post a modified post with the same attachments but without posting any file. The exisisting attachment will be reused', end='')
    # msg_id = logbook.post('Modified post. Check the logbook folder, there should be only one copy of each attachment file with the original timestamp', attributes=attributes,msg_id=msg_id)
    # print('........ DONE!')
    #
    # print('Reading back the logbook entry', end='')
    # msg, attrs, attachs2 = logbook.read(msg_id)
    # print('........ DONE!')
    # if attachs2 == attachs:
    #     print('Verified attachment timestamps are OK.')
    # else:
    #     print('Something did not work!')

    print('Modifing one attachment file', end='')
    generate_attachment_file('attach1.txt', 'modified test')
    print('........ DONE!')

    print('Attempting to post a modified post with two attachments. One has the same name as before, but different content. '
          'The other attachment will be reused', end='')
    msg_id = logbook.post('Modified post. Check the logbook folder, there should be only one copy '
                          'of each attachment file with the original timestamp', attributes=attributes,
                          msg_id=msg_id, attachments=attachment_list)
    print('........ DONE!')

    print('Reading back the logbook entry', end='')
    msg, attrs, attachs = logbook.read(msg_id)
    print('........ DONE!')

    print('Those are the attachments on the server')
    for attach in attachs:
        print(f' --> {attach}')
    print('Check that there are no others')

# print('post originale fatto con solo 1 attachment')



    # with open('attach1.txt', 'w') as file:
    #     file.write('contenuto mod')
    #
    #
    #
    # msg_id = logbook.post('modified post', msg_id=msg_id, attributes=attributes, attachments=attachments)
    # print('post modificato fatto con due attachements')
    #
    # msg_id = logbook.post('post finale. in questo momento non sto caricando nessun attachments, ma dovrebbero rimanere',
    #                       msg_id=msg_id, attributes=attributes)
    # print('post file fatto con due attachements')
    #
    # message, attributes, attachments = logbook.read(msg_id)
    #
    #
    # # attributes['jcmd'] = ''
    # attributes['delatt0'] = 'Delete'
    #
    # # del attributes['attachment0']
    # msg_id = logbook.post('ho cancellato a mano delatt0',
    #                      msg_id=msg_id, attributes=attributes)
    # print('delete att0')
    #

if __name__ == '__main__':
    main()