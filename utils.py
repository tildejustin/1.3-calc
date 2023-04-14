import os
import subprocess
from typing import Union

#
# # stolen from easy-multi
# def take_arg(string: str, ind: int) -> str:
#     """Takes a single argument or word from a string.
#     Args:
#         string (str): utf-8 string containing multiple words.
#         ind (int): Starting index of argument.
#     Returns:
#         str: The argument at the specified `index` of `string`.
#     """
#     sub = string[ind:]
#     if sub == "":
#         return ""
#     while sub[0] == " ":
#         sub = sub[1:]
#         if sub == "":
#             return ""
#     if sub[0] == '"':
#         scan_ind = 1
#         bsc = 0
#         while scan_ind < len(sub):
#             if sub[scan_ind] == "\\":
#                 bsc += 1
#             elif sub[scan_ind] == '"':
#                 if bsc % 2 == 0:
#                     break
#                 else:
#                     bsc = 0
#             else:
#                 bsc = 0
#             scan_ind += 1
#         if scan_ind == len(sub):
#             raise  # QUOTATION WAS NOT ENDED
#         return sub[1:scan_ind].encode("utf-8").decode("unicode_escape")
#     else:
#         scan_ind = 1
#         while scan_ind < len(sub) and scan_ind:
#             if sub[scan_ind] == " ":
#                 break
#             scan_ind += 1
#         return sub[:scan_ind]


def check_dir(pid: int, dir: str) -> Union[str, None]:
    # Thanks to the creator of MoveWorlds-v0.3.ahk (probably specnr)
    cmd = f'powershell.exe "$proc = Get-WmiObject Win32_Process -Filter \\"ProcessId = {str(pid)}\\";$proc.CommandLine"'
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    response = p.communicate()[0].decode()
    if dir in response:
        start = response.index(dir)
        end = response.index(r"/", start+len(dir)+1)
        return response[start:end]
    return None
