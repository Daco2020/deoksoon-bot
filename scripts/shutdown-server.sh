#!/bin/bash

set -ex

kill $(cat temp-pid) && rm temp-pid