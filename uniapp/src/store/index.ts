import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  // 从本地存储恢复用户信息
  const stored = uni.getStorageSync('userInfo')
  const userInfo = ref<any>(stored || null)
  const isLoggedIn = ref(!!stored)

  function setUserInfo(info: any) {
    userInfo.value = info
    isLoggedIn.value = true
    uni.setStorageSync('userInfo', info)
  }

  function logout() {
    userInfo.value = null
    isLoggedIn.value = false
    uni.removeStorageSync('accessToken')
    uni.removeStorageSync('refreshToken')
    uni.removeStorageSync('tokenExpiry')
    uni.removeStorageSync('userInfo')
  }

  return { userInfo, isLoggedIn, setUserInfo, logout }
})
