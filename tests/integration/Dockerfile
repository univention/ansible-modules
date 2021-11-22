FROM univention/univention-corporate-server

ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && \
		apt install -y locales python-pip python-cairo-dev python3-pip python3-cairo-dev && \
		apt autoremove -y && \
		rm -rf /var/lib/apt/lists/*

RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
		dpkg-reconfigure --frontend=noninteractive locales && \
		update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8
