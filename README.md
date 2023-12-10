# Jinn
<p align="center">
  <img src="https://raw.githubusercontent.com/one-two-four-cee-four-one-plus/jinn/main/logo.png" width="250" height="250"/>
</p>
Have you ever wanted to own a <a href="https://en.wikipedia.org/wiki/Jinn">genie</a> in a <a href="https://bottlepy.org/">bottle</a>? Now you can.
Jinn is a straightforward web app that harnesse the power of OpenAI's ChatGPT to provide users with a capable, wish-fulfilling machine. Currently developed as a solution to overcome OpenAI's restrictions on code interpreters, Jinn enables ChatGPT to access an unrestricted execution environment. It also allows users to interact with it via web and API.
The primary goal is to be as simple as possible, as accessible as a phone conversation, yet powerful enough to accomplish non-trivial tasks. All the while, it maintains transparency regarding the assistant's context and actions.

### Installation
Since Jinn can ocasionally install new packages, it is recommended to run it in a virtual environment or docker container. Latter is the preferred method, as it is more secure and easier to manage. Download the repository and run docker build in the root directory:
```
docker build -t jinn .
```
Then run the container:
```
docker run -d -p 8080:8080 jinn
```
Jinn uses /var/www/data to store sqlite3 database and logs. You can mount it to a local directory to preserve data between container restarts:
```
docker run -d -p 8080:8080 -v /path/to/local/data:/var/www/data jinn
```
Root user login/password can be set via environment variables:
```
docker run -d -p 8080:8080 -e USER=user -e PASSWORD=pass jinn
```
Jinn will create a new user when database is empty.

### Usage
Jinn tries to fulfill user's wish by using various python functions generated for previous requests or tailored specifically for current one. This means that you should directly prompt Jinn to do what you want it to do. You don't ask a question, like you do with chatGPT.

Jinn can be accessed via web interface or API. Web interface is available at http://localhost:8080. API is available at http://localhost:8080/api. Main API endpoint is http://localhost:8080/api/wish. It accepts POST requests with JSON body:
```bash
http -pBb POST 'http:/localhost:8080/api/wish' Authorization:'Bearer <token>' text='get bitcoin price'
{
    "text": "get bitcoin price"
}


43893.3896
```
In addition Jinn can understand voice commands and return audio file with spoken text, when request body contains audio file. This is controlled by Content-Type & Accept headers.

### Configuration
Configuration is done via web interface. It is available at http://localhost:8080/config. Only non-default required configuration is OpenAI API key. It can be obtained at https://platform.openai.com/api-keys. Jinn will automatically create a new user when database is empty. This user will have admin rights and can be used to make changes to configuration.