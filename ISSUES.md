# Found issues during testing

* The existence of locations is not checked when saving/validating
* When incorrect settings are saved, there is no way to go back to editing this backup yml via the web interface
* I skipped the scheduling, because I first wanted to do a manual run, and never reached the checking of connections/gmail
* The log output seems to me to indicate the GMail credentials are not checked after saving the settings. It would be nice if this is encountered there would appear a button to the settings and testing to appear.
    INFO backup_server.config_file — Reading backup config from '/data/backup_config.yml'
    INFO backup_server.config_file — Found task 'TestBackup'
    ERROR backup_server.backup_task — Cannot reach back-up local destination '/mnt/pool/backup_test/local'
    INFO backup_server.database — Storing run information of 'TestBackup' to 'log.db'
    [ERROR] (535, b'5.7.8 Username and Password not accepted. For more information, go to\n5.7.8  https://support.google.com/mail/?p=BadCredentials 4fb4d7f45d1cf-673032b9e83sm2245077a12.4 - gsmtp')