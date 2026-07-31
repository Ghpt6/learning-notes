
# /etc/hosts
192.168.88.101 node1
192.168.88.102 node2
192.168.88.103 node3

ssh-keygen -t rsa -b 4096

ssh-copy-id node1
ssh-copy-id node2
ssh-copy-id node3

useradd hadoop
passwd hadoop
1234
su - hadoop
ssh-keygen -t rsa -b 4096
ssh-copy-id node1
ssh-copy-id node2
ssh-copy-id node3


mkdir -p /export/server
tar -zxvf OpenJDK8U-jdk_x64_linux_hotspot_8u492b09.tar.gz -C /export/server
ln -s /export/server/jdk8u492-b09 /export/server/jdk


export JAVA_HOME=/export/server/jdk
export PATH=$PATH:$JAVA_HOME/bin

source /etc/profile

rm -f /usr/bin/java
ln -s /export/server/jdk/bin/java /usr/bin/java

java -version
javac -version

systemctl stop firewalld
systemctl disable firewalld

vim /etc/sysconfig/selinux

SELINUX=disabled

systemctl status firewalld


# 安装ntp软件
cd /etc/yum.repos.d/

mkdir -p bak
mv *.repo bak/
# 创建新的 CentOS 7 repo：


cat > /etc/yum.repos.d/CentOS-Base.repo <<'EOF'
[base]
name=CentOS-7.9.2009 - Base
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/os/$basearch/
gpgcheck=1
gpgkey=https://mirrors.aliyun.com/centos-vault/RPM-GPG-KEY-CentOS-7
enabled=1

[updates]
name=CentOS-7.9.2009 - Updates
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/updates/$basearch/
gpgcheck=1
gpgkey=https://mirrors.aliyun.com/centos-vault/RPM-GPG-KEY-CentOS-7
enabled=1

[extras]
name=CentOS-7.9.2009 - Extras
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/extras/$basearch/
gpgcheck=1
gpgkey=https://mirrors.aliyun.com/centos-vault/RPM-GPG-KEY-CentOS-7
enabled=1

[centosplus]
name=CentOS-7.9.2009 - Plus
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/centosplus/$basearch/
gpgcheck=1
gpgkey=https://mirrors.aliyun.com/centos-vault/RPM-GPG-KEY-CentOS-7
enabled=0
EOF
# 清理并重建缓存：


yum clean all
yum makecache
# 然后安装：


yum install -y ntp

# 更新时区
rm -f /etc/localtime
sudo ln -s /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

# 同步时间
ntpdate -u ntp.aliyun.com

# 开启ntp服务并设置开机自启
systemctl start ntpd
systemctl enable ntpd



#####HDFS配置
tar -zxvf hadoop-3.3.5.tar.gz -C /export/server

cd /export/server
ln -s /export/server/hadoop-3.3.5 hadoop
cd hadoop


# workers 配置DataNode
cat > etc/hadoop/workers <<EOF
node1
node2
node3
EOF

cat etc/hadoop/workers

# hadoop-env.sh 配置hadoop环境
cat >> etc/hadoop/hadoop-env.sh <<'EOF'
export JAVA_HOME=/export/server/jdk
export HADOOP_HOME=/export/server/hadoop
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
export HADOOP_LOG_DIR=$HADOOP_HOME/logs
EOF

tail etc/hadoop/hadoop-env.sh

# core-site.xml 核心配置(node1)
<configuration>
    <property>
        <name>fs.defaultFS</name>
        <value>hdfs://node1:8020</value>
    </property>
    <property>
        <name>io.file.buffer.size</name>
        <value>131072</value>
    </property>
</configuration>

# hdfs-site.xml 
<configuration>
    <property>
        <name>dfs.datanode.data.dir.perm</name>
        <value>700</value>
    </property>
    <property>
        <name>dfs.namenode.name.dir</name>
        <value>/data/nn</value>
    </property>
    <property>
        <name>dfs.namenode.hosts</name>
        <value>node1,node2,node3</value>
    </property>
    <property>
        <name>dfs.blocksize</name>
        <value>268435456</value>
    </property>
    <property>
        <name>dfs.namenode.handler.count</name>
        <value>100</value>
    </property>
    <property>
        <name>dfs.datanode.data.dir</name>
        <value>/data/dn</value>
    </property>
</configuration>

# node1
mkdir -p /data/nn
mkdir /data/dn

# node2,3
mkdir -p /data/dn


# 分发hadoop文件夹
scp -r hadoop-3.3.5 node2:`pwd`/
scp -r hadoop-3.3.5 node3:`pwd`/
# node2,3
ln -s /export/server/hadoop-3.3.5 /export/server/hadoop


cat >> /etc/profile <<'EOF'
export HADOOP_HOME=/export/server/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
EOF

tail -5 /etc/profile

source /etc/profile


chown -R hadoop:hadoop /data
chown -R hadoop:hadoop /export


# 格式化整个文件系统
su - hadoop
hadoop namenode -format
# start
start-dfs.sh
# stop
stop-dfs.sh

# end----刚刚部署好HDFS集群


# YARN 集群部署开始(3台nodes都要，通过scp分发或者全部执行一遍)


# mapreduce配置文件
# 在$HADOOP_HOME/etc/hadoop 文件夹内，修改: *mapred-env.sh*

cat >> etc/hadoop/mapred-env.sh <<'EOF'
# 设置JDK路径
export JAVA_HOME=/export/server/jdk

# 设置JobHistoryServer进程内存为1G
export HADOOP_JOB_HISTORYSERVER_HEAPSIZE=1000

# 设置日志级别为INFO
export HADOOP_MAPRED_ROOT_LOGGER=INFO,RFA
EOF

tail -3 etc/hadoop/mapred-env.sh 

# mapred-site.xml

cat > etc/hadoop/mapred-site.xml <<'EOF'
<?xml version="1.0"?>
<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>
<configuration>
    <property>
        <name>mapreduce.framework.name</name>
        <value>yarn</value>
        <description>MapReduce的运行框架设置为YARN</description>
    </property>

    <property>
        <name>mapreduce.jobhistory.address</name>
        <value>node1:10020</value>
        <description>历史服务器通讯端口为node1:10020</description>
    </property>

    <property>
        <name>mapreduce.jobhistory.webapp.address</name>
        <value>node1:19888</value>
        <description>历史服务器web端口为node1的19888</description>
    </property>

    <property>
        <name>mapreduce.jobhistory.intermediate-done-dir</name>
        <value>/data/mr-history/tmp</value>
        <description>历史信息在HDFS的记录临时路径</description>
    </property>

    <property>
        <name>mapreduce.jobhistory.done-dir</name>
        <value>/data/mr-history/done</value>
        <description>历史信息在HDFS的记录路径</description>
    </property>

    <property>
        <name>yarn.app.mapreduce.am.env</name>
        <value>HADOOP_MAPRED_HOME=$HADOOP_HOME</value>
        <description>MapReduce HOME 设置为 HADOOP_HOME</description>
    </property>

    <property>
        <name>mapreduce.map.env</name>
        <value>HADOOP_MAPRED_HOME=$HADOOP_HOME</value>
        <description>MapReduce HOME 设置为 HADOOP_HOME</description>
    </property>

    <property>
        <name>mapreduce.reduce.env</name>
        <value>HADOOP_MAPRED_HOME=$HADOOP_HOME</value>
        <description>MapReduce HOME 设置为 HADOOP_HOME</description>
    </property>
</configuration>
EOF

clear
tail -5 etc/hadoop/mapred-site.xml


# yarn配置文件
# yarn-env.sh

cat >> etc/hadoop/yarn-env.sh <<'EOF'
# 设置JDK路径的环境变量
export JAVA_HOME=/export/server/jdk

# 设置HADOOP_HOME的环境变量
export HADOOP_HOME=/export/server/hadoop

# 设置配置文件路径的环境变量
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop

# 设置日志文件路径的环境变量
export HADOOP_LOG_DIR=$HADOOP_HOME/logs
EOF



# yarn-site.xml

cat > etc/hadoop/yarn-site.xml <<'EOF'
<?xml version="1.0"?>
<configuration>
<property>
    <name>yarn.resourcemanager.hostname</name>
    <value>node1</value>
    <description>ResourceManager设置在node1节点</description>
</property>

<property>
    <name>yarn.nodemanager.local-dirs</name>
    <value>/data/nm-local</value>
    <description>NodeManager中间数据本地存储路径</description>
</property>

<property>
    <name>yarn.nodemanager.log-dirs</name>
    <value>/data/nm-log</value>
    <description>NodeManager数据日志本地存储路径</description>
</property>

<property>
    <name>yarn.nodemanager.aux-services</name>
    <value>mapreduce_shuffle</value>
    <description>为MapReduce程序开启Shuffle服务</description>
</property>

<property>
    <name>yarn.log.server.url</name>
    <value>http://node1:19888/jobhistory/logs</value>
    <description>历史服务器URL</description>
</property>

<property>
    <name>yarn.web-proxy.address</name>
    <value>node1:8089</value>
    <description>代理服务器主机和端口</description>
</property>

<property>
    <name>yarn.log-aggregation-enable</name>
    <value>true</value>
    <description>开启日志聚合</description>
</property>

<property>
    <name>yarn.nodemanager.remote-app-log-dir</name>
    <value>/tmp/logs</value>
    <description>程序日志HDFS的存储路径</description>
</property>

<property>
    <name>yarn.resourcemanager.scheduler.class</name>
    <value>org.apache.hadoop.yarn.server.resourcemanager.scheduler.fair.FairScheduler</value>
    <description>选择公平调度器</description>
</property>
</configuration>
EOF

# 一键启停yarn集群
start-yarn.sh
stop-yarn.sh

# 历史服务器
bin/mapred --daemon start historyserver

# end----刚刚部署好yarn集群



# hive配置

# 安装mysql

# 更新密钥
rpm --import https://repo.mysql.com/RPM-GPG-KEY-mysql-2023

# 安装MySQL yum库
rpm -Uvh http://repo.mysql.com/mysql57-community-release-el7-7.noarch.rpm

# yum安装MySQL
yum -y install mysql-community-server

# 启动MySQL并设置开机启动
systemctl start mysqld
systemctl enable mysqld

# 检查MySQL服务状态
systemctl status mysqld

# 第一次启动MySQL，会在日志文件中生成root用户的一个随机密码，使用下面命令查看该密码
grep 'temporary password' /var/log/mysqld.log

# 如果你想设置简单密码，需要降低MySQL的密码安全级别
set global validate_password_policy=LOW;   # 密码安全级别低
set global validate_password_length=4;     # 密码长度最低4位即可

# 然后就可以用简单密码了（课程中使用简单密码，为了方便，生产中不要这样）
ALTER USER 'root'@'localhost' IDENTIFIED BY '1234';

grant all privileges on *.* to root@"%" identified by '1234' with grant option;

flush privileges;   


# hadoop配置

# core-site.xml中增加并分发到其他服务器
<property>
    <name>hadoop.proxyuser.hadoop.hosts</name>
    <value>*</value>
</property>
<property>
    <name>hadoop.proxyuser.hadoop.groups</name>
    <value>*</value>
</property>


# 分发，重启
scp etc/hadoop/core-site.xml node2:`pwd`/etc/hadoop/core-site.xml
scp etc/hadoop/core-site.xml node3:`pwd`/etc/hadoop/core-site.xml

stop-yarn.sh 
stop-dfs.sh

start-dfs.sh
start-yarn.sh

# hive安装
tar -zxvf apache-hive-3.1.3-bin.tar.gz -C /export/server/
ln -s /export/server/apache-hive-3.1.3-bin /export/server/hive


# mysql driver
https://repo1.maven.org/maven2/mysql/mysql-connector-java/5.1.34/mysql-connector-java-5.1.34.jar
# 将下载好的驱动jar包放入Hive安装目录的lib目录
mv mysql-connector-java-5.1.48.jar /export/server/hive/lib/



# 在Hive的conf目录内，新建hive-env.sh文件
export HADOOP_HOME=/export/server/hadoop

export HIVE_CONF_DIR=/export/server/hive/conf

export HIVE_AUX_JARS_PATH=/export/server/hive/lib


# hive-site.xml
<configuration>

    <property>
        <name>javax.jdo.option.ConnectionURL</name>
        <value>jdbc:mysql://node1:3306/hive?createDatabaseIfNotExist=true&amp;useSSL=false&amp;useUnicode=true&amp;characterEncoding=UTF-8</value>
    </property>

    <property>
        <name>javax.jdo.option.ConnectionDriverName</name>
        <value>com.mysql.jdbc.Driver</value>
    </property>

    <property>
        <name>javax.jdo.option.ConnectionUserName</name>
        <value>root</value>
    </property>

    <property>
        <name>javax.jdo.option.ConnectionPassword</name>
        <value>1234</value>
    </property>

    <property>
        <name>hive.server2.thrift.bind.host</name>
        <value>node1</value>
    </property>

    <property>
        <name>hive.metastore.uris</name>
        <value>thrift://node1:9083</value>
    </property>

    <property>
        <name>hive.metastore.event.db.notification.api.auth</name>
        <value>false</value>
    </property>

</configuration>


# 初始化元数据库
CREATE DATABASE hive CHARSET UTF8;
# 执行元数据库初始化命令
cd /export/server/hive
bin/schematool -initSchema -dbType mysql -verbose


# 启动hive

# 创建日志目录
mkdir /export/server/hive/logs

# 启动元数据管理服务（必须启动，否则无法工作）
# 前台启动
bin/hive --service metastore
# 后台启动
nohup bin/hive --service metastore >> logs/metastore.log 2>&1 &

# 启动客户端（二选一，当前先选择Hive Shell方式）
# Hive Shell方式（可以直接写SQL）
bin/hive
# Hive ThriftServer方式（不可直接写SQL，需要外部客户端连接使用）
bin/hive --service hiveserver2

# end----hive刚刚配置完成



#---------------run in node1
start-dfs.sh
start-yarn.sh
/export/server/hadoop/bin/mapred --daemon start historyserver
nohup /export/server/hive/bin/hive --service metastore >> /export/server/hive/logs/metastore.log 2>&1 &
