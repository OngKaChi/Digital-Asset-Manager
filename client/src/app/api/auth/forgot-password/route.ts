import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

export async function POST(request: NextRequest) {
  let payload: unknown
  try {
    payload = await request.json()
  } catch {
    return NextResponse.json({ detail: "Invalid request body." }, { status: 400 })
  }

  try {
    const backendResponse = await fetch(`${BACKEND_URL}/api/auth/forgot-password/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    })

    const data = await backendResponse.json().catch(() => ({}))
    const response = NextResponse.json(data, { status: backendResponse.status })

    return response
  } catch (error) {
    console.error("Forgot-password backend request failed", error)
    return NextResponse.json(
      { detail: "Could not connect to the Django backend." },
      { status: 502 },
    )
  }

}
