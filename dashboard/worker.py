#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Standard library imports
import json
import time

# Imports from third party packages
import redis
import requests
import yaml


REFRESH_INTERVAL = 1  # seconds


class RedisUpdater(object):
    def __init__(self, api_url, secret):
        self.api_url = api_url
        self.params = {"secret": secret}
        self.redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

    def ctf_services(self):
        services = {}
        url = '/'.join([self.api_url, 'getgameinfo'])
        services_info = requests.get(url, params=self.params).json()['services']
        for service_info in services_info:
            service_id = service_info['service_id']
            if service_id not in services:
                services[service_id] = {}

            services[service_id]['description'] = service_info['description']
            services[service_id]['port'] = service_info['internal_port']
            services[service_id]['name'] = service_info['service_name']
            services[service_id]['flag_id'] = \
                {'description': service_info['flag_id_description']}

        self.store_redis('ctf_services', json.dumps(services))
        return

    def ctf_services_status(self):
        url = '/'.join([self.api_url, "getservicesstate"])
        r = requests.get(url, params=self.params)
        self.store_redis('ctf_services_status', json.dumps(r.json()["teams"]))
        return

    def ctf_teams(self):
        url = '/'.join([self.api_url, "getgameinfo"])
        r = requests.get(url, params=self.params)
        teams_data = r.json()["teams"]
        teams = {}
        for team_data in teams_data:
            team_id = int(team_data["team_id"])
            teams[team_id] = {"team_id": team_id,
                              "team_name": team_data["team_name"]}

        self.store_redis('ctf_teams', json.dumps(teams))
        return

    def ctf_scores(self):
        url = '/'.join([self.api_url, "getgameinfo"])
        r = requests.get(url, params=self.params)
        teams_data = r.json()["teams"]
        teams_names = {}
        for team_data in teams_data:
            teams_names[team_data["team_id"]] = team_data["team_name"]

        url = '/'.join([self.api_url, "scores"])
        r = requests.get(url, params=self.params)
        scores_data = r.json()["scores"]
        scores = []
        for team in scores_data:
            team_id = int(team)
            scores.append(scores_data[team])
            scores[-1]["team_name"] = teams_names[team_id]

        scores.sort(key=lambda x: (x["score"], x['sla']), reverse=True)
        self.store_redis('ctf_scores', json.dumps(scores))

    def ctf_exploits(self):
        url = '/'.join([self.api_url, "getgameinfo"])
        r = requests.get(url, params=self.params)
        teams_data = r.json()["teams"]
        teams_names = {}
        for team_data in teams_data:
            teams_names[team_data["team_id"]] = team_data["team_name"]

        services_data = r.json()["services"]
        services_names = {}
        for service_data in services_data:
            services_names[service_data["service_id"]] = service_data["service_name"]

        url = '/'.join([self.api_url, "exploitlogs"])
        r = requests.get(url, params=self.params)
        raw_exploits_logs = r.json()["exploits_logs"]
        exploits_logs = {}
        for raw_entry in raw_exploits_logs:
            attacker = teams_names[raw_entry["attacker_id"]]
            defender = teams_names[raw_entry["defender_id"]]
            service = services_names[raw_entry["service_id"]]
            if attacker not in exploits_logs:
                exploits_logs[attacker] = {}

            if service not in exploits_logs[attacker]:
                exploits_logs[attacker][service] = {}

            if raw_entry['success'] == 1:
                data = {'stdout': "",
                        'stderr': "",
                        'success': raw_entry['success']
                        }
            else:
                data = {'stdout': raw_entry['stdout'],
                        'stderr': raw_entry['stderr'],
                        'success': raw_entry['success']
                        }
            exploits_logs[attacker][service][defender] = data

        self.store_redis('ctf_exploits', json.dumps(exploits_logs))
        return

    def store_redis(self, key, value):
        self.redis_client.set(key, value)
        return


def main():
    config_file = "config.yml"
    fh = open(config_file)
    config = yaml.load(fh.read())
    fh.close()
    redis_updater = RedisUpdater(config["api_base_url"], config["api_secret"])
    methods_to_run = [member for member in dir(redis_updater) if
                      member.startswith("ctf_") and '__func__' in
                      dir(getattr(redis_updater, member))]
    while True:
        for method in methods_to_run:
            print("Refreshing %s" % (method))
            getattr(redis_updater, method)()

        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
