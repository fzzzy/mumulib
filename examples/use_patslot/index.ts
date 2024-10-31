import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';

const readFileAsync = (filePath: string) => {
  return new Promise<Buffer>((resolve, reject) => {
    fs.readFile(filePath, (err, data) => {
      if (err) {
        reject(err);
      } else {
        resolve(data);
      }
    });
  });
};

const server = http.createServer(async (req, res) => {
  try {
    if (req.url === '/') {
      const data = await readFileAsync(path.join(__dirname, 'index.html'));
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(data);
    } else if (req.url === '/patslot_example.js') {
      const data = await readFileAsync(path.join(__dirname, 'patslot_example.js'));
      res.writeHead(200, { 'Content-Type': 'application/javascript' });
      res.end(data);
    } else {
      res.writeHead(404);
      res.end('Not Found');
    }
  } catch (err) {
    res.writeHead(500);
    res.end('Error loading file');
  }
});

server.listen(3000, () => {
  console.log('Server is listening on port 3000');
});
