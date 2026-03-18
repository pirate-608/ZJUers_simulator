import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import App from './App.vue'

describe('App.vue', () => {
    it('renders correctly', () => {
        const wrapper = mount(App, {
            global: {
                plugins: [createTestingPinia({
                    stubActions: false, // 让 pinia 正常工作而不全是 stub
                })],
            },
        })
        expect(wrapper.exists()).toBe(true)
    })
})
