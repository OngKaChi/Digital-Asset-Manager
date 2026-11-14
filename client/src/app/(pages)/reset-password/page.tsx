import ResetPassword from "@/components/auth/ResetPassword"
import ThemeToggle from "@/components/ui/ThemeToggle"
import { Flex, Heading, Stack, Text } from "@chakra-ui/react"

interface ResetPasswordPageProps {
  searchParams: Promise<{
    uid?: string
    token?: string
  }>
}

export default async function ResetPasswordPage({
  searchParams,
}: ResetPasswordPageProps) {
  const { uid, token } = await searchParams

  return (
    <Flex
      minH="100vh"
      w="full"
      align="center"
      justify="center"
      px={{ base: 4, md: 6 }}
      py={{ base: 12, md: 16 }}
      gap={6}
    >
      <ThemeToggle />
      <Stack gap={6} align="center">
        <Stack gap={2} textAlign="center">
          <Heading size="lg">Reset your password</Heading>
          <Text color="gray.500">Enter and confirm your new password.</Text>
        </Stack>
        <ResetPassword uid={uid} token={token} />
      </Stack>
    </Flex>
  )
}
