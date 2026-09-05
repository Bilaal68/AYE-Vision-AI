from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "vulnerable_target_active",
        "notice": "Isolated Adversary Simulation Environment target"
    })

@app.route('/vulnerable-endpoint', methods=['GET', 'POST'])
def vulnerable_endpoint():
    cmd = request.args.get('cmd', '')
    return jsonify({"received_cmd": cmd, "warning": "Simulated vulnerability target"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
