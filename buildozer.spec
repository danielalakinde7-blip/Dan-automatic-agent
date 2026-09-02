[app]
title = DAN Automation Agent
package.name = danautomation
package.domain = com.gamemaster
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json
version = 0.1
requirements = python3,kivy==2.3.0,kivymd,requests,pyjnius,plyer,certifi,charset-normalizer,idna,urllib3,beautifulsoup4,soupsieve
orientation = portrait
fullscreen = 0

android.permissions = INTERNET,CAMERA,FLASHLIGHT,VIBRATE,RECORD_AUDIO,READ_CONTACTS,CALL_PHONE,SEND_SMS,READ_SMS,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECEIVE_BOOT_COMPLETED,WAKE_LOCK

android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
p4a.branch = master

[buildozer]
log_level = 2
