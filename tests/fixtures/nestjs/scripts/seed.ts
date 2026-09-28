// One-off seed script, run outside Nest's DI container via ts-node.
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  await prisma.$disconnect();
}

main();
