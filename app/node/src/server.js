import http from "node:http";

const port = Number(process.env.PORT ?? 3000);

const server = http.createServer((req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify({ service: "kya-node-gateway", status: "ok" }));
});

server.listen(port, () => {
  console.log(`kya-node-gateway listening on ${port}`);
});
