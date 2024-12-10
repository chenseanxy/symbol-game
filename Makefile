installfb:
	wget https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-7.17.26-linux-x86_64.tar.gz
	tar -zxvf filebeat-7.17.26-linux-x86_64.tar.gz
	rm -rf filebeat-7.17.26-linux-x86_64.tar.gz
	mv filebeat-7.17.26-linux-x86_64/ /home/user/.local/share/
	ln -s /home/user/.local/share/filebeat-7.17.26-linux-x86_64/filebeat /home/user/.local/bin/filebeat

filebeat:
	@chmod go-w /home/user/Desktop/symbol-game/filebeat.yml
	@filebeat -c /home/user/Desktop/symbol-game/filebeat.yml -e
