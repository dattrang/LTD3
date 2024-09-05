import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# Thiết lập API Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SHEET_ID = '1P_37Z1vRN97BtwNQtNlf5CHbhb1ee60i_yLlv2ichpo'
RANGE_NAME = 'Main!A:X'

# Kết nối tới Google Sheets
def get_google_sheets_data():
    credentials = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=SHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])

    if not values:
        return pd.DataFrame()
    else:
        # Chuyển dữ liệu thành DataFrame
        df = pd.DataFrame(values[1:], columns=values[0])
        
        # Lọc các cột cần thiết
        columns_to_keep = ['Date', 'Name', 'Phone', 'thuTuc', 'Status', 'Done', 'CTV', 'User', 'Password']
        missing_columns = [col for col in columns_to_keep if col not in df.columns]

        if missing_columns:
            st.write(f"Các cột bị thiếu: {', '.join(missing_columns)}")
            return pd.DataFrame()  # Trả về DataFrame rỗng nếu có cột thiếu

        df_filtered = df[columns_to_keep]  # Lọc những cột bạn muốn giữ lại

        # Chuyển cột 'Date' thành kiểu datetime
        df_filtered['Date'] = pd.to_datetime(df_filtered['Date'], format='%d/%m/%Y', errors='coerce')

        # Loại bỏ các hàng có giá trị 'Date' không hợp lệ (NaT)
        df_filtered = df_filtered.dropna(subset=['Date'])

        return df_filtered

# Hàm tính hoa hồng cho từng ngày
def calculate_commission_for_day(success_count):
    if success_count < 15:
        return success_count * 10000, 0.20
    elif 15 <= success_count <= 25:
        return success_count * 12000, 0.24
    else:
        return success_count * 15000, 0.30

# Tính tổng hoa hồng cho từng ngày trong khoảng thời gian
def calculate_total_commission(df, start_date, end_date):
    # Chỉ lấy các đơn 'Đã thanh toán'
    df_paid = df[df['Done'] == 'Đã thanh toán']

    # Nhóm theo ngày và đếm số lượng đơn 'Đã thanh toán' mỗi ngày
    daily_success = df_paid.groupby(df_paid['Date'].dt.date).size()

    # Tạo dãy ngày đầy đủ từ start_date đến end_date
    full_date_range = pd.date_range(start=start_date, end=end_date)

    # Reindex để đảm bảo rằng tất cả các ngày đều có mặt (kể cả các ngày không có dữ liệu)
    daily_success = daily_success.reindex(full_date_range, fill_value=0)

    # Tính tổng hoa hồng
    total_commission = 0
    for day, success_count in daily_success.items():
        commission, _ = calculate_commission_for_day(success_count)
        total_commission += commission

    return total_commission, daily_success

# Lọc dữ liệu theo cộng tác viên và ngày
def filter_data_by_user_and_date(df, user, start_date, end_date):
    # Lọc theo user (CTV)
    filtered_df = df[df['CTV'] == user]

    # Lọc theo khoảng thời gian
    filtered_df = filtered_df[(filtered_df['Date'] >= pd.Timestamp(start_date)) & (filtered_df['Date'] <= pd.Timestamp(end_date))]
    
    return filtered_df

# Streamlit app
def main():
    # Lấy dữ liệu từ Google Sheets, bao gồm cả cột 'User' và 'Password'
    df = get_google_sheets_data()
    st.title('Bảng theo dõi tổng hợp hoa hồng')
    sta = st.empty()
    sta.write('Vui lòng đăng nhập để sử dụng')
    # Phần đăng nhập
    st.sidebar.title("Đăng nhập")

    # Nếu session_state chưa có giá trị đăng nhập, thì thiết lập mặc định là False
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    # Nếu người dùng chưa đăng nhập
    if not st.session_state.logged_in:
        # Sử dụng session_state để lưu trữ user và password tạm thời, ngăn chặn việc tải lại trang khi nhập
        if "user_input" not in st.session_state:
            st.session_state.user_input = ""
        if "password_input" not in st.session_state:
            st.session_state.password_input = ""

        # Input User ID và mật khẩu
        st.session_state.user_input = st.sidebar.text_input("User ID", value=st.session_state.user_input)
        st.session_state.password_input = st.sidebar.text_input("Password", type="password", value=st.session_state.password_input)

        # Nút Đăng nhập
        login_button = st.sidebar.button("Đăng nhập")

        # Kiểm tra thông tin đăng nhập
        if login_button:
            # Kiểm tra xem user và password có tồn tại trong dữ liệu không
            user_row = df[(df['User'] == st.session_state.user_input) & (df['Password'] == st.session_state.password_input)]

            if not user_row.empty:
                st.session_state.logged_in = True
                st.session_state.user = st.session_state.user_input  # Lưu user vào session state
                st.success("Đăng nhập thành công!")
                sta.empty()
            else:
                st.error("Thông tin đăng nhập không đúng!")
    
    # Nếu người dùng đã đăng nhập
    if st.session_state.logged_in:
        # Lựa chọn ngày bắt đầu và ngày kết thúc sau khi đăng nhập
        st.sidebar.subheader("Lọc theo ngày")
        start_date = st.sidebar.date_input("Ngày bắt đầu", datetime.today().replace(day=1))  # Mặc định là ngày đầu tiên của tháng hiện tại
        end_date = st.sidebar.date_input("Ngày kết thúc", datetime.today())  # Mặc định là ngày hiện tại

        # Nút Lọc
        filter_button = st.sidebar.button("Lọc")

        # Nếu người dùng nhấn nút "Lọc"
        if filter_button:
            # Lọc dữ liệu theo user (CTV) và khoảng thời gian
            user_data = filter_data_by_user_and_date(df, st.session_state.user, start_date, end_date)
            sta.empty()

            # Trực quan hóa dữ liệu bằng biểu đồ
            if not user_data.empty:
                # Tính tổng tiền hoa hồng cho khoảng thời gian đã lọc, chỉ dựa trên dữ liệu đã thanh toán
                total_commission, daily_success = calculate_total_commission(user_data, start_date, end_date)

                # Hiển thị tổng tiền hoa hồng
                formatted_total_commission = "{:,.0f} VND".format(total_commission).replace(",", ".")
                st.header(f"Tổng tiền hoa hồng: {formatted_total_commission}")
                
                # Hiển thị toàn bộ dữ liệu (không chỉ đã thanh toán)
                st.write(f"Dữ liệu của Cộng tác viên: {st.session_state.user}")
                # Loại bỏ 2 cột cuối bằng iloc
                user_data_trimmed = user_data.iloc[:, :-3]

                # Hiển thị DataFrame mới
                st.dataframe(user_data_trimmed)

                # Trực quan hóa biểu đồ toàn bộ dữ liệu 'Done'
                if 'Done' in user_data.columns:
                    # Tính số lượng từng loại trạng thái thanh toán
                    done_counts = user_data['Done'].value_counts()
                    # Chuẩn bị chuỗi hiển thị
                    status_summary = "Tổng số lượng theo trạng thái thanh toán:\n"
                    for status, count in done_counts.items():
                        status_summary += f"- {status}: {count} đơn\n"

                    # Hiển thị kết quả bằng st.write
                    st.write(status_summary)

                    # Ngoài ra, bạn vẫn có thể hiển thị biểu đồ thanh nếu cần
                    st.bar_chart(done_counts)

                # Trực quan hóa biểu đồ toàn bộ dữ liệu 'Status'
                if 'Status' in user_data.columns:
                    status_counts = user_data['Status'].value_counts()
                    status_summary2 = "Tổng số lượng theo trạng thái hồ sơ:\n"
                    for status, count in status_counts.items():
                        status_summary2 += f"- {status}: {count} Hồ sơ\n"
                    st.write(status_summary2)
                    st.bar_chart(status_counts)

                # Hiển thị số lượng đơn đã thanh toán mỗi ngày (bao gồm các ngày có giá trị = 0)
                st.write("Số lượng đơn Đã thanh toán mỗi ngày:")
                st.line_chart(daily_success)

            else:
                st.write("Không có dữ liệu để hiển thị.")

if __name__ == "__main__":
    main()
