import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

export async function POST(request: NextRequest) {
  const payload = await request.json()

  const backendResponse = await fetch(`${BACKEND_URL}/api/auth/reset-password/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  })

  const data = await backendResponse.json().catch(() => ({}))
  return NextResponse.json(data, { status: backendResponse.status })
}
