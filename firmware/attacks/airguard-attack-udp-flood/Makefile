CONTIKI_PROJECT = udp-client udp-server
all: $(CONTIKI_PROJECT)

# The AirGuard firmware lives outside the Contiki-NG source tree.
# Override CONTIKI from the command line when using another installation path.
CONTIKI ?= /home/ubuntu/contiki-ng
PROJECT_CONF_PATH = project-conf.h

include $(CONTIKI)/Makefile.include
