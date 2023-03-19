import requests
import json
import shutil
import time
import os
from io import BufferedReader
from pathlib import Path

_DEFAULT_PATH = os.path.dirname(os.path.abspath(__file__)) + "/"

class Gofile:
    def __init__(self,email:str=None,token:str=None):
        self.email = email
        self.token = token
        self.user_data = {}
        self.s = self._login()
        self.server = self._get_server()

    def _token_login(self,session:requests.Session,token=None):
        if not token:
            token = self.token
        session.get(f"https://gofile.io/login/{token}") # this will never fail even with invalid token
        login_resp = session.get(f"https://api.gofile.io/getAccountDetails?token={token}")
        if login_resp.status_code == 304:
            return session # it means the account info already exists in local storage, probably will never be triggered in this code
        elif login_resp.status_code == 200 and login_resp.json()["status"] == "ok":
            # logged in
            self.user_data.update(login_resp.json()["data"])
            self.token = token
            return session
        elif login_resp.status_code == 401 and login_resp.json()["status"] == "error-auth":
            # invalid token
            raise Exception("Invalid token")
        else:
            pass

    def _login(self):
        sess = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 OPR/94.0.0.0",
                "Sec-Ch-Ua": '"Chromium";v="108", "Opera";v="94", "Not)A;Brand";v="99"'}
        if self.token:
            return self._token_login(sess)
        if self.email:
            email = self.email.replace("@","%40")
            sess.get(f"https://api.gofile.io/createAccount?email={email}",headers=headers)
            token = input("Please check your email (spam box as well) and paste the link here: ").strip()[-32:]
            return self._token_login(sess,token=token)
        else:
            resp = sess.get("https://api.gofile.io/createAccount")
            token = resp.json()["data"]["token"]
            return self._token_login(sess,token=token)
        
    def _api_request(self,reqtype:str,uri:str=None,payload=None,field=None,host="https://api.gofile.io",files=None):
        if not uri:
            dest = host
        else:
            if uri.startswith(("https://","http://")):
                dest = uri
            else:
                if not uri.startswith("/"):
                    uri = "/" + uri
                dest = host + uri
        reqtype = reqtype.upper()
        if type(payload) == dict:
            if type(files) == bool and files == True:
                resp = self.s.request(reqtype,dest,files=payload)
            elif type(files) == dict:
                resp = self.s.request(reqtype,dest,json=payload,files=files)
            else:
                resp = self.s.request(reqtype,dest,json=payload)
        elif type(payload) == str:
            resp = self.s.request(reqtype,dest,data=payload)
        else:
            resp = self.s.request(reqtype,dest)

        try:
            resp = resp.json()
        except json.decoder.JSONDecodeError or requests.exceptions.JSONDecodeError or ValueError:
            pass

        if field:
            if field in resp:
                return resp[field]
        else:
            return resp

    def _get_server(self):
        return self._api_request("get","/getServer",None,"data")["server"]
    
    def _construct_files_dict(self,file:bytes|BufferedReader,folder_id=None,filename:str=None):
        if filename:
            file_tuple = (filename,file)
        if type(file) == BufferedReader:
            if filename:
                raise Exception("File is passed as BufferedReader and a filename is set. Please remove filename and try again or pass the file in bytes")
            file_tuple = file

        files = {
            'file':file_tuple,
            'token':(None,self.token)
        }

        if folder_id:
            files.update({'folderId':(None,folder_id)})
        else:
            files.update({'folderId':(None,self.user_data["rootFolder"])})

        return files

    def _upload_files(self,file:bytes|BufferedReader|list,folder_id=None,filename:str=None):
        if type(file) == list:
            results = []
            for data in file:
                files = self._construct_files_dict(data,folder_id,filename)
                result = self._api_request("post","/uploadFile",files,"data",host=f'https://{self.server}.gofile.io',files=True)
                results.append(result)
            return results
        else:
            files = self._construct_files_dict(file,folder_id,filename)
            return self._api_request("post","/uploadFile",files,"data",host=f'https://{self.server}.gofile.io',files=True)

    def _upload_path(self,path:str,folder_id=None,isdir=False):

        if not folder_id:
            folder_id = self.user_data["rootFolder"]

        if "\\" in path: #windows dir correction
            path = path.replace("\\","/")

        if isdir: #directory
            if not path.endswith("/"):
                path += "/"
            top_folder_name = path.rstrip("/").split("/")[-1]
            top_folder = self._create_folder(top_folder_name,folder_id)
            top_folder_id = top_folder["id"]
            folders = {path:top_folder_id}
            results = []
            for dp,dn,fn in os.walk(path): # dirpath,dirnames,filenames 
                if "\\" in dp: #windows dir correction
                    dp = dp.replace("\\","/")
                if not dp.endswith("/"):
                    dp += "/"
                current_folder = folders[dp]
                files = []
                if dn: #deez nuts hahahaha kill me
                    for dirname in dn:
                        folder_attrs = self._create_folder(dirname,current_folder)
                        folders.update({dp+dirname+"/" : folder_attrs["id"]})
                if fn:
                    for filedata in fn:
                        buf = open(dp+filedata,"rb")
                        files.append(buf)
                result = self._upload_files(files,current_folder)
                results.append(result)
            return results

        else: #single file
            buf = open(path,"rb")
            return self._upload_files(buf,folder_id)

    def _get_content(self,content_id):
       resp = self._api_request("get",f"/getContent?contentId={content_id}&token={self.token}&websiteToken=12345")
       if "data" in resp and resp["data"]:
           return resp["data"]
       else:
           return resp

    def _download_req(self,url:str=None,localpath:str=_DEFAULT_PATH,empty_dir=False):
        if empty_dir:
            localpath = localpath.replace("\\","/")
            with Path(localpath) as p:
                p.mkdir(parents=True,exist_ok=True)
            return localpath
        else:
            filename = url.split('/')[-1]
            without_ext,ext = filename.rsplit(".",1)
            if localpath.endswith(filename):
                filepath = localpath
                folderpath = localpath.rsplit("/",1)[0]
            else:
                filepath = localpath + without_ext + "." + ext
                folderpath = localpath
            i = 1
            with self.s.get(url, stream=True) as r:
                correct_size = int(r.headers["Content-Length"])
                while True:
                    try:
                        with Path(folderpath) as p:
                            p.mkdir(parents=True,exist_ok=True)
                        with open(filepath, "xb") as f:
                            shutil.copyfileobj(r.raw, f,length=16*1024*1024)
                        if correct_size == len(Path(filepath).read_bytes()):
                            return filepath
                        else:
                            #print(f"{correct_size} {len(Path(filepath).read_bytes())}")
                            os.remove(filepath)
                            raise Exception("File sizes do not match, try again")
                    except FileExistsError:
                        filepath = folderpath+"/"+without_ext+f" ({i})."+ext
                        i += 1
                
    def _sort_dict(self,d:dict,nested=None):
        if nested:
            return dict(sorted(d.items(), key=lambda item: item[1][nested]))
        else:
            return dict(sorted(d.items(), key=lambda item: item[1]))

    def _make_path_strs(self,top_folder_id:str):
        paths = {}
        root_info = self._get_content(top_folder_id)
        root_name = root_info["name"]
        root_id = root_info["id"] #necessary for public links
        all_contents = self._fetch(root_id,recursive=True)
        #print(all_contents)
        files_only = {k: v for k, v in all_contents.items() if v["type"] == "file"}
        folders_only = {k: v for k, v in all_contents.items() if v["type"] == "folder"}
        empty_folders_only = {k: v for k, v in folders_only.items() if v["childs"] == []}
        target_contents = {}
        target_contents.update(files_only)
        target_contents.update(empty_folders_only)
        for v in target_contents.values():
            parent_id = v["parentFolder"]
            #print(parent_id)
            path = "/" + v["name"]
            while True:
                if parent_id == root_id:
                    path = root_name+path
                    break
                parent_dict = all_contents[parent_id]
                if parent_dict["id"] == root_id:
                    path = root_name+path
                    break
                _name,_id = parent_dict["name"],parent_dict["parentFolder"]
                path = "/"+_name+path
                parent_id = _id
                #print(f"\n{paths}\n")
            if "childs" in v:
                if v["childs"] == []:
                    path += "/"
                    paths.update({path:None})
            else:        
                paths.update({path:v["link"]})
        return paths

    def _download(self,url:str=None,id:str=None,default_path:str=_DEFAULT_PATH):
        self.s.cookies.update({"accountToken":self.token})
        downloaded = []
        if url:
            folder_id = url.rsplit("/",1)[-1]
        elif id:
            folder_id = id
        elif url and id:
            raise Exception("Please pass only either Content ID or URL.")
        else: #downloading entire account
            folder_id = self.user_data["rootFolder"]

        if default_path.endswith("\\"):
            default_path = default_path.rstrip("\\") + "/"
        if not default_path.endswith("/"):
            default_path = default_path + "/"

        for path,link in self._make_path_strs(folder_id).items():
            path = default_path + path
            if path.endswith("/") and link == None:
                downloaded_file = self._download_req(localpath=path,empty_dir=True)
            else:
                downloaded_file = self._download_req(link,path)
            downloaded.append(downloaded_file)
        return downloaded

    def _create_folder(self,folder_name:str,parent_folder_id=None):
        if not parent_folder_id:
            parent_folder_id = self.user_data["rootFolder"]

        payl = {
            "parentFolderId":parent_folder_id,
            "token":self.token,
            "folderName":folder_name
        }

        return self._api_request("put","/createFolder",payl,"data")
    
    def _fetch(self,folder=None,recursive=False,ext_link:str=None):
        if not folder:
            folder = self.user_data["rootFolder"]
        contents = {}
        if ext_link:
            folder = ext_link.split("/")[-1]
        if recursive:
            folders = [folder]
            for folder_id in folders:
                try:
                    data_dict = self._get_content(folder_id)
                    contents.update(data_dict["contents"])
                except KeyError: #ratelimit 
                    while True:
                        if "status" in data_dict:
                            if data_dict["status"] == "error-rateLimit":
                                time.sleep(1)
                                print("Rate limited, please be patient")
                                time.sleep(5)
                                data_dict = self._get_content(folder_id)
                            else:
                                print(data_dict)
                        else:
                            contents.update(data_dict["contents"])
                            break
                data_dict = self._get_content(folder_id)
                try:
                    for content_id in data_dict["childs"]:
                        if data_dict["contents"][content_id]["type"] == "folder":
                            folders.append(content_id)
                except KeyError: # shows that the content at that moment is not a folder
                    pass
                        
        else:
            contents.update(self._get_content(folder)["contents"])

        return contents

    def _change_folder_option(self,folder_id:str,option:str,value:str):
        payl = {
            "folderId": folder_id,
            "token": self.token,
            "option": option,
            "value": value
        }
        return self._api_request("put","/setFolderOption",payl,"status")

    def _copy_contents(self,contents_id:str|list,folder_id:str):
        if type(contents_id) == list:
            contents_id = ",".join(contents_id)

        payl = {
            "contentsId":contents_id,
            "folderIdDest":folder_id,
            "token":self.token
        }

        return self._api_request("put","/copyContent",payl,"status")
    
    def _delete_contents(self,contents_id:str|list):
        if type(contents_id) == list:
            contents_id = ",".join(contents_id)
        payl = {
            "contentsId":contents_id,
            "token":self.token
        }

        return self._api_request("delete","/deleteContent",payl,"status")
    
    def search_content(self,name:str,folder:str=None,recursive=False):
        """
        """
        result = {}
        for k,v in self._fetch(folder,recursive).items():
            if v["name"] == name:
                result.update({k:v})
        return result

    def delete_contents(self,contents_id:str|list):
        """
        Deletes content(s)
        ### Parameters:
            - contents_id (str|list): Content ID of content, multiple contents can be passed at the same time with a list
        """
        return self._delete_contents(contents_id)

    def copy_contents(self,contents_id:str|list,folder_id:str):
        """
        Copies content(s) (Premium account only)
        ### Parameters:
            - contents_id (str|list): Content ID of content, multiple contents can be passed at the same time with a list
            - folder_id (str): Content ID of destination folder
        """
        return self._copy_contents(contents_id,folder_id)
    
    def change_folder_option(self,folder_id:str,option:str,value):
        """
        Changes folder option
        ### Parameters:
            - folder_id (str): Content ID of folder 
            - option (str): The option that is to be changed
            - value (str): The new value of the option
        ### Possible options and values:
            - public (bool): States the privacy of the folder
            - password (str): New password of the folder
            - description (str): New description of the folder
            - expire (int): The expiry date of the folder in timestamp
            - tags (list): The list of the new tags
        """
        if option == "tags" and type(value) == list:
            value = ",".join(value)
        return self._change_folder_option(folder_id,option,value)
    
    def create_folder(self,folder_name:str,parent_folder_id:str=None):
        """
        Creates folder
        ### Parameters:
            - folder_name (str): Name of folder that is to be created
            - parent_folder_id (str): Folder that the new folder will be created in. Default: Root folder
        """
        return self._create_folder(folder_name,parent_folder_id)

    def upload_raw(self,file:bytes|BufferedReader|list,folder_id=None,filename:str=None,):
        """
        Uploads files using raw file data

        ### Parameters:
            - file (bytes|BufferedReader|list*): The file in bytes or BufferedReader object or multiple files in list as BufferedReader objects*
            - folder_id (str): Content ID of destination folder. Default: Root folder
            - filename (str): The filename*
            
        #### Note: 
        #### Always use BufferedReader when passing a list of files!!

        It is recommended to pass the file as BufferedReader object and leave the filename parameter empty when passing a single file. E.g:

            `with open("/path/to/the/file.txt","rb") as b:`
                `g.upload_file(b,"example_folder_id")`

        Use file bytes and filename only if it's needed to upload the file with a different name.
        """
        return self._upload_files(file,filename,folder_id)
    
    def upload(self,path:str,folder_id:str=None):
        """
        Uploads files via path

        ### Parameters:
            - path (str): The path to the file/folder that will be uploaded
            - folder_id (str): Content ID of destination folder. Default: Root folder
        """
        if os.path.isdir(path):
            return self._upload_path(path,folder_id,isdir=True)
        elif os.path.isfile(path):
            return self._upload_path(path,folder_id,isdir=False)

    def download_folder(self,url:str=None,id:str=None,default_path:str=_DEFAULT_PATH):
        """
        Downloads the entire folder from given URL or Content ID recursively.

        ### Parameters:
            - url (str): The URL of folder
            - id (str): The Content ID of folder
            - default_path (str): Path that the folder will be downloaded to. 

        #### Pass either URL or ID but not both

        #### Cannot download single files at the moment

        #### If neither is given, download the entire root folder instead
        """

        return self._download(url,id,default_path)

