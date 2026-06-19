/**
 * M0 wallet generation. Creates an AUTHOR (payee) and a BUYER (funder) wallet and
 * writes them to .env. Adapted from arc-nanopayments/generate-wallets.mts
 * (Apache-2.0, Circle) — see NOTICE. Run: `npm run generate-wallets`.
 */
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import fs from "node:fs";
import path from "node:path";

const envPath = path.resolve(".env");

function gen(label: string) {
  const privateKey = generatePrivateKey();
  const { address } = privateKeyToAccount(privateKey);
  console.log(`\n${label}\n  Address:     ${address}\n  Private key: ${privateKey}`);
  return { address, privateKey };
}

const author = gen("Author (payee — receives the citation toll)");
const buyer = gen("Buyer (funder — bankrolls the agent; FUND THIS via faucet)");

const values: Record<string, string> = {
  AUTHOR_ADDRESS: author.address,
  AUTHOR_PRIVATE_KEY: author.privateKey,
  BUYER_ADDRESS: buyer.address,
  BUYER_PRIVATE_KEY: buyer.privateKey,
};

let content = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf-8") : "";
if (!content) content = fs.readFileSync(path.resolve(".env.example"), "utf-8");
for (const [k, v] of Object.entries(values)) {
  const re = new RegExp(`^${k}=.*$`, "m");
  const line = `${k}=${v}`;
  content = re.test(content) ? content.replace(re, line) : content.trimEnd() + "\n" + line;
}
fs.writeFileSync(envPath, content.trimEnd() + "\n");

console.log(`\nWritten to ${envPath}`);
console.log(`\nNext:
  1. Fund BUYER  ${buyer.address}  with Arc testnet USDC: https://faucet.circle.com/
  2. Fund AUTHOR ${author.address} too if you want it to pay its own gas later (not needed for M0).
  3. Terminal A: npm run seller
  4. Terminal B: npm run m0`);
