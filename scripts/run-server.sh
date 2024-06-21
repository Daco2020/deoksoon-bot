#!/bin/bash

set -ex

nohup python main.py & echo $! > temp-pid