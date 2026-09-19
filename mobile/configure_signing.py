import os
import re

kts_path = 'android/app/build.gradle.kts'
groovy_path = 'android/app/build.gradle'

if os.path.exists(kts_path):
    with open(kts_path, 'r', encoding='utf-8') as f:
        content = f.read()

    signing_code = """
    signingConfigs {
        create("release") {
            keyAlias = "tableverse"
            keyPassword = "tableverse_key_2026"
            storeFile = file("../keystore/release.jks")
            storePassword = "tableverse_key_2026"
            enableV1Signing = true
            enableV2Signing = true
        }
    }
"""
    if 'signingConfigs {' not in content:
        content = content.replace('buildTypes {', signing_code + '\n    buildTypes {')

    content = content.replace('signingConfig = signingConfigs.getByName("debug")', 'signingConfig = signingConfigs.getByName("release")')
    content = re.sub(r'targetSdk\s*=\s*\S+', 'targetSdk = 35', content)
    content = re.sub(r'compileSdk\s*=\s*\S+', 'compileSdk = 35', content)
    content = re.sub(r'minSdk\s*=\s*\S+', 'minSdk = 21', content)
    if 'ndkVersion' not in content:
        content = content.replace('android {', 'android {\n    ndkVersion = "27.0.12077973"')

    with open(kts_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Updated build.gradle.kts with permanent release signing and SDK 35')

elif os.path.exists(groovy_path):
    with open(groovy_path, 'r', encoding='utf-8') as f:
        content = f.read()

    signing_code = """
    signingConfigs {
        release {
            keyAlias 'tableverse'
            keyPassword 'tableverse_key_2026'
            storeFile file('../keystore/release.jks')
            storePassword 'tableverse_key_2026'
            v1SigningEnabled true
            v2SigningEnabled true
        }
    }
"""
    if 'signingConfigs {' not in content:
        content = content.replace('buildTypes {', signing_code + '\n    buildTypes {')

    content = re.sub(r'signingConfig\s+signingConfigs\.debug', 'signingConfig signingConfigs.release', content)
    content = re.sub(r'compileSdk\s*=\s*\d+', 'compileSdk = 35', content)
    content = re.sub(r'targetSdk\s*=\s*\d+', 'targetSdk = 35', content)
    content = re.sub(r'minSdk\s*=\s*\d+', 'minSdk = 21', content)
    if 'ndkVersion' not in content:
        content = content.replace('android {', 'android {\n    ndkVersion "27.0.12077973"')

    with open(groovy_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Updated build.gradle with permanent release signing and SDK 35')
else:
    print('Warning: No build.gradle or build.gradle.kts found.')
