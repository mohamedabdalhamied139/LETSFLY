import os

manifest_path = os.path.join("android", "app", "src", "main", "AndroidManifest.xml")
if os.path.exists(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Add permissions before <application
    perms = '    <uses-permission android:name="android.permission.INTERNET"/>\n    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>\n    <application'
    if "<uses-permission android:name=\"android.permission.INTERNET\"/>" not in content:
        content = content.replace("<application", perms, 1)

    # Add usesCleartextTraffic="true" to <application
    if 'android:usesCleartextTraffic' not in content:
        content = content.replace("<application", '<application android:usesCleartextTraffic="true"', 1)

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully patched AndroidManifest.xml")
else:
    print(f"Error: {manifest_path} not found")
