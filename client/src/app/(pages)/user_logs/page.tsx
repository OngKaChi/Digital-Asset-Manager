"use client"

import { Stack } from "@chakra-ui/react"

import PrivateRoute from "@/components/auth/PrivateRoute"
import UserLogsList from "@/components/UserLogs/UserLogsList"
import Header from "@/components/ui/Header"
import Sidebar from "@/components/ui/Sidebar"

export default function UserLogsPage() {
  return (
    <PrivateRoute roles={["superadmin", "admin"]} redirectTo="/dashboard">
      {(user) => (
        <Sidebar user={user}>
          <Stack gap={6}>
            <Header
              title="User Logs"
              description="Review user and authentication activity."
            />
            <UserLogsList />
          </Stack>
        </Sidebar>
      )}
    </PrivateRoute>
  )
}
