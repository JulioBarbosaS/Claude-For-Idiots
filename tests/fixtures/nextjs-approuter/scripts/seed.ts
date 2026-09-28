// Referenced from package.json's "prisma": { "seed": "tsx scripts/seed.ts" }.
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  await prisma.$disconnect();
}

main();
