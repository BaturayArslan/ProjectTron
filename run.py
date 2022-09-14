from drawProject.factory import  create_app

if __name__ == '__main__':
    app = create_app(test=True)
    app.run(host='0.0.0.0')