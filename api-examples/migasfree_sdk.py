#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import requests
import json
import csv
import platform
import subprocess


class ApiToken():
    _ok_codes = [
        requests.codes.ok, requests.codes.created,
        requests.codes.moved, requests.codes.found,
        requests.codes.temporary_redirect, requests.codes.resume
    ]
    server = ""
    user = ""
    headers = {"content-type": "application/json"}
    protocol = "http"
    proxies = {'http': "", "https": ""}
    version = 1

    def __init__(self, server="", user="", token="", save_token=False, version=1):
        self.server = server
        if not self.server:
            try:
                from migasfree_client.utils import get_config
                from migasfree_client import settings as client_settings
                config = get_config(client_settings.CONF_FILE, 'client')
                self.server = config.get('server', 'localhost')
            except ImportError:
                self.server = self.get_server()

        self.user = user
        self.version = version
        if token:
            self.set_token(token)
        else:
            if not self.user:
                self.user = self.get_user()

            _token_file = self.token_file()
            if not os.path.exists(_token_file):
                password = self.get_password()
                if password:
                    data = {"username": self.user, "password": password}
                    r = requests.post(
                        "%s://%s/token-auth/" % (self.protocol, self.server),
                        headers=self.headers,
                        data=json.dumps(data),
                        proxies=self.proxies
                    )
                    if r.status_code in self._ok_codes:
                        self.set_token(r.json()["token"])
                        if save_token:
                            with open(_token_file, 'w') as handle:
                                handle.write(r.json()["token"])
                    else:
                        print r.json()
                        raise Exception('Status code %s' % r.status_code)
            else:
                with open(_token_file, "r") as handle:
                    self.set_token(handle.read())

    def set_token(self, token):
        self.headers['authorization'] = "Token %s" % token

    def url(self, endpoint):
        return "%s://%s/api/v%s/token/%s/" % \
            (self.protocol, self.server, self.version, endpoint)

    def url_id(self, endpoint, id):
        return "%s%s/" % (self.url(endpoint), id)

    def paginate(self, endpoint, params={}):  # GET
        return requests.get(
            self.url(endpoint),
            headers=self.headers,
            params=params,
            proxies=self.proxies
        ).json()

    def post(self, endpoint, data):  # POST
        return requests.post(
            self.url(endpoint),
            headers=self.headers,
            data=json.dumps(data),
            proxies=self.proxies
        )

    def delete(self, endpoint, id):  # DELETE ID
        return requests.delete(
            self.url_id(endpoint, id),
            headers=self.headers,
            proxies=self.proxies
        )

    def patch(self, endpoint, id, data):  # PATCH ID
        return requests.patch(
            self.url_id(endpoint, id),
            headers=self.headers,
            data=json.dumps(data),
            proxies=self.proxies
        )

    def put(self, endpoint, id, data):  # PUT ID
        return requests.put(
            self.url_id(endpoint, id),
            headers=self.headers,
            data=json.dumps(data),
            proxies=self.proxies
        )

    def get(self, endpoint, param):
        """
        param can be 'id' or '{}'
        return only one object or exception
        """
        if isinstance(param, (long, int)):  # GET ID
            r = requests.get(
                self.url_id(endpoint, param),
                headers=self.headers,
                params={},
                proxies=self.proxies
            )
            if r.status_code in self._ok_codes:
                return r.json()
            else:
                raise Exception('Status code %s' % r.status_code)
        else:
            r = requests.get(
                self.url(endpoint),
                headers=self.headers,
                params=param,
                proxies=self.proxies
            )
            if r.status_code in self._ok_codes:
                data = r.json()
                if data["count"] == 1:
                    return data["results"][0]
                elif data["count"] == 0:
                    raise Exception('Not found')
                else:
                    raise Exception('Multiple records found')
            else:
                raise Exception('Status code %s' % r.status_code)

    def filter(self, endpoint, params={}):  # iterator
        url = self.url(endpoint)
        while url:
            r = requests.get(
                url,
                headers=self.headers,
                params=params,
                proxies=self.proxies
            )
            if r.status_code in self._ok_codes:
                data = r.json()
                for element in data["results"]:
                    yield element
                url = data["next"]

    def add(self, endpoint, data):
        r = self.post(endpoint, data=data)
        if r.status_code == requests.codes.created:
            return r.json()["id"]
        else:
            print r.json()
            Exception('Status code %s' % r.status_code)

    @staticmethod
    def is_ok(status):
        return status == requests.codes.ok

    @staticmethod
    def is_created(status):
        return status == requests.codes.created

    @staticmethod
    def is_forbidden(status):
        return status == requests.codes.forbidden

    def id(self, endpoint, params):
        return self.get(endpoint, params)['id']

    @staticmethod
    def getUserPath():
        _platform = platform.system()
        if _platform == 'Linux':
            _env = "HOME"
        elif _platform == 'Windows':
            _env = "USERPROFILE"
        return os.getenv(_env)

    def token_file(self):
        return os.path.join(
            self.getUserPath(),
            ".migasfree-token.%s" % self.user
        )

    def get_server(self):
        cmd = "zenity --title 'MigasfreeApiSdk' --entry --text='Server:' --entry-text='localhost' 2>/dev/null"
        try:
            server = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, shell=True
            )
        except:
            server = "localhost"
        return server.replace("\n", "")

    def get_user(self):
        cmd = "zenity --title 'MigasfreeApiSdk @ %s' --entry --text='User:' 2>/dev/null" % (
            self.server
        )
        try:
            user = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, shell=True
            )
        except:
            user = ""
        return user.replace("\n", "")

    def get_password(self):
        cmd = "zenity --title 'MigasfreeApiSdk  %s @ %s' --password 2>/dev/null" % (
            self.user,
            self.server
        )
        try:
            password = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, shell=True
            )
        except:
            password = ""
        return password.replace("\n", "")

    def csv(self, endpoint, params={}, fields=[], output="output.csv"):

        def render_line(element, fields):
            line = {}
            for keys in fields:
                x = element
                for key in keys.split('.'):
                    x = x[key]
                    line[keys] = x
            return line

        with open(output, 'wb') as csvfile:
            if fields:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()
            for element in self.filter(endpoint, params):
                if not fields:
                    fields = element.keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fields)
                    writer.writeheader()
                writer.writerow(render_line(element, fields))


if __name__ == '__main__':
    api = ApiToken(
        token="9c8afd1fa3512c05f2366b3502ddd78ffb06d8d5"
    )

    print
    print "--------------------------------"
    print "La segunda pagina de atributos"
    print api.paginate("attributes", {"page": 2})

    print
    print "--------------------------------"
    print "Todos los atributos PCI"
    for x in api.filter("attributes", {"property_att__prefix": "PCI"}):
        print x["value"], x["description"]

    print
    print "--------------------------------"
    print "Crea un Conjunto de Atributos"
    r = api.post("attribute-set", {
        "excluded_attributes": [],
        "included_attributes": [],
        "enabled": True,
        "name": "NUEVO",
        "description": "POST - nuevo conjunto"
        }
    )
    print r, r.json()

    print
    print "--------------------------------"
    print "Modificar todo el Conjunto de Atributos"
    j = api.put("attribute-set", r.json()["id"], {
        "excluded_attributes": [],
        "included_attributes": [],
        "enabled": True,
        "name": "NUEVO",
        "description": "PUT- modificado"
        }
    )
    print j, j.json()

    print
    print "--------------------------------"
    print "Modificar el campo descripcion de un Conjunto de Atributos"
    d = api.patch("attribute-set", r.json()["id"], {"description": "HOLA"})
    print d, d.json()

    print
    print "--------------------------------"
    print "Borrar el Conjunto de Atributos"
    h = api.delete("attribute-set", r.json()["id"])
    print h

    print
    print "--------------------------------"
    print "Obtener el id de un elemento"
    print api.id("computers", {"name": 'PC25619'})

    print
    print "--------------------------------"
    print "Obtener un elemento"
    print api.get("computers", {"name": 'PC25619'})["uuid"]

    print
    print "--------------------------------"
    print "El Ordenador 4855"
    x = api.get("computers", 4855)
    print x["name"], x["uuid"]

    api = ApiToken(
        # server="127.0.0.1"
        # user="reader",
        # save_token=True,
        token="9c8afd1fa3512c05f2366b3502ddd78ffb06d8d5"
    )

    fields = [
        'id', 'name', 'product', 'cpu', 'ram', 'disks',
        'storage', 'project.name', 'mac_address', 'ip_address'
    ]
    output = "hardware.csv"
    api.csv(
        'computers',
        {"status": "intended", "ordering": "id"},
        fields,
        output
    )
    os.system("xdg-open %s" % output)