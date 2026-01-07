def main(ctx):
    print("hello, there is a plugin named hello.")
    print("the lastest release version is: ")
    print(f"{ctx['version']}")
    
    # 在main.py文件的元数据中添加新的数据
    ctx['data'].append("hello plugin has comed here")